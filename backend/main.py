import datetime
import os
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from typing import Optional, List, Dict
from dotenv import load_dotenv

from data_fetcher import resolve_symbol, fetch_stock_data
from model import train_and_predict

load_dotenv(Path(__file__).with_name(".env"))

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "algorise-dev-secret")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

mongo_client = None
users_collection = None
mongo_ready = False

app = FastAPI(
    title="Algorise Stock LSTM Predictor API",
    description="Backend for stock prediction using PyTorch LSTM models and Twelve Data.",
    version="1.0.0"
)

# Enable CORS for React frontend (running locally on port 3000 or similar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this. For local/HF dev, '*' is fine.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PredictionRequest(BaseModel):
    company_name: str = Field(..., description="Full company name or search query, e.g. Apple")
    tenure: str = Field(..., description="Prediction tenure: 1h, 1d, 2d, 1w, or 1m")
    api_key: Optional[str] = Field(None, description="Optional Twelve Data API key")


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    user_id: str = Field(..., min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=1, max_length=128)


class AuthUser(BaseModel):
    name: str
    user_id: str
    email: EmailStr


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser

class StockPoint(BaseModel):
    time: str
    value: float

class PredictionResponse(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    is_mocked: bool
    historical: List[StockPoint]
    predicted: List[StockPoint]
    last_price: float
    predicted_end_price: float
    percentage_change: float


def get_users_collection():
    global mongo_client, users_collection, mongo_ready

    if not MONGODB_URI:
        raise HTTPException(
            status_code=500,
            detail="MONGODB_URI is not configured. Add it to backend/.env before using authentication.",
        )

    if users_collection is not None:
        return users_collection

    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        database = mongo_client.get_default_database()
        if database is None:
            database = mongo_client["algorise"]

        users_collection = database["users"]

        if not mongo_ready:
            users_collection.create_index([("user_id", ASCENDING)], unique=True)
            users_collection.create_index([("email", ASCENDING)], unique=True)
            mongo_ready = True

        return users_collection
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"MongoDB connection failed: {str(exc)}")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expiry}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def serialize_user(user_doc) -> AuthUser:
    return AuthUser(
        name=user_doc["name"],
        user_id=user_doc["user_id"],
        email=user_doc["email"],
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

    users = get_users_collection()
    user_doc = users.find_one({"user_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Authenticated user not found.")

    return serialize_user(user_doc)


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(request: SignupRequest):
    users = get_users_collection()

    normalized_user_id = request.user_id.strip()
    normalized_email = request.email.lower()

    if users.find_one({"user_id": normalized_user_id}):
        raise HTTPException(status_code=400, detail="User ID already exists.")

    if users.find_one({"email": normalized_email}):
        raise HTTPException(status_code=400, detail="Email is already registered.")

    user_document = {
        "name": request.name.strip(),
        "user_id": normalized_user_id,
        "email": normalized_email,
        "password_hash": hash_password(request.password),
        "created_at": datetime.datetime.utcnow(),
    }

    try:
        users.insert_one(user_document)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="User ID or email already exists.")

    token = create_access_token(normalized_user_id)
    return AuthResponse(access_token=token, user=serialize_user(user_document))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest):
    users = get_users_collection()
    normalized_user_id = request.user_id.strip()
    user_doc = users.find_one({"user_id": normalized_user_id})

    if not user_doc or not verify_password(request.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid user ID or password.")

    token = create_access_token(user_doc["user_id"])
    return AuthResponse(access_token=token, user=serialize_user(user_doc))


@app.get("/api/auth/me", response_model=AuthUser)
def read_current_user(current_user: AuthUser = Depends(get_current_user)):
    return current_user

# Mapping of tenure options to Twelve Data parameters
TENURE_MAPPING = {
    "1h": {"interval": "5min", "predict_steps": 12, "outputsize": 120},
    "1d": {"interval": "1h", "predict_steps": 24, "outputsize": 200},
    "2d": {"interval": "1h", "predict_steps": 48, "outputsize": 200},
    "1w": {"interval": "1day", "predict_steps": 7, "outputsize": 60},
    "1m": {"interval": "1day", "predict_steps": 30, "outputsize": 120},
}

def generate_future_timestamps(start_time_str: str, interval: str, steps: int) -> List[str]:
    """
    Generates a list of future timestamp strings starting after the given start time.
    """
    is_daily = (interval == "1day")
    
    # Try parsing format
    if is_daily:
        try:
            start_dt = datetime.datetime.strptime(start_time_str, "%Y-%m-%d")
        except ValueError:
            # Fallback to date portion if has hours
            start_dt = datetime.datetime.strptime(start_time_str.split()[0], "%Y-%m-%d")
    else:
        try:
            start_dt = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                start_dt = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                # Fallback to current time
                start_dt = datetime.datetime.now()

    future_times = []
    curr_dt = start_dt
    
    # Define timedelta based on interval
    if interval == "5min":
        delta = datetime.timedelta(minutes=5)
    elif interval == "1h":
        delta = datetime.timedelta(hours=1)
    else: # 1day
        delta = datetime.timedelta(days=1)
        
    for _ in range(steps):
        curr_dt += delta
        # If daily, skip weekends to look realistic
        if is_daily:
            while curr_dt.weekday() >= 5: # Saturday = 5, Sunday = 6
                curr_dt += delta
                
        if is_daily:
            future_times.append(curr_dt.strftime("%Y-%m-%d"))
        else:
            future_times.append(curr_dt.strftime("%Y-%m-%d %H:%M:%S"))
            
    return future_times


@app.get("/api/search")
def search_company(q: str, api_key: Optional[str] = None, current_user: AuthUser = Depends(get_current_user)):
    """
    Endpoint to search and select a company by name.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
        
    resolved = resolve_symbol(q, api_key)
    # We return a list to allow frontend autocomplete dropdown support
    return [resolved]


@app.post("/api/predict", response_model=PredictionResponse)
def predict_stock(request: PredictionRequest, current_user: AuthUser = Depends(get_current_user)):
    """
    Predicts stock prices based on the company name and selected tenure.
    Trains an LSTM model on the fly and returns historical and predicted points.
    """
    # 1. Resolve company name to ticker symbol
    resolved = resolve_symbol(request.company_name, request.api_key)
    symbol = resolved["symbol"]
    company_name = resolved["name"]
    exchange = resolved["exchange"]
    
    # 2. Get tenure configuration
    tenure_config = TENURE_MAPPING.get(request.tenure.lower())
    if not tenure_config:
        raise HTTPException(status_code=400, detail=f"Invalid tenure: {request.tenure}")
        
    interval = tenure_config["interval"]
    predict_steps = tenure_config["predict_steps"]
    outputsize = tenure_config["outputsize"]
    
    print(f"Prediction Request for {company_name} ({symbol}) | Tenure: {request.tenure} | Interval: {interval}")
    
    # 3. Fetch historical data
    historical_records, is_mocked = fetch_stock_data(symbol, interval, outputsize, request.api_key)
    
    if not historical_records or len(historical_records) < 10:
        raise HTTPException(
            status_code=500, 
            detail=f"Insufficient historical data fetched for symbol {symbol}. Please try again later."
        )
        
    # 4. Extract closing prices
    prices = [r["close"] for r in historical_records]
    
    # 5. Train LSTM model and predict future prices
    print("Training PyTorch LSTM Neural Network on backend...")
    
    def log_epoch(epoch, total, loss):
        print(f"Epoch {epoch}/{total} | Loss: {loss:.6f}")
        
    try:
        predictions = train_and_predict(
            prices=prices,
            seq_length=15,
            predict_steps=predict_steps,
            epochs=50,
            epoch_callback=log_epoch
        )
    except Exception as e:
        print(f"LSTM training error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Machine learning model training failed: {str(e)}"
        )
        
    # 6. Construct response structures
    # Historical data list
    historical_points = [
        StockPoint(time=r["datetime"], value=r["close"])
        for r in historical_records
    ]
    
    # Generate future timestamps
    last_historical_time = historical_records[-1]["datetime"]
    future_times = generate_future_timestamps(last_historical_time, interval, predict_steps)
    
    # Predicted data list
    predicted_points = []
    # To make the chart continuous, start the predicted line at the last historical price
    predicted_points.append(
        StockPoint(time=last_historical_time, value=historical_records[-1]["close"])
    )
    
    for t, val in zip(future_times, predictions):
        predicted_points.append(
            StockPoint(time=t, value=round(val, 2))
        )
        
    # 7. Calculate stats
    last_price = float(historical_records[-1]["close"])
    predicted_end_price = float(predictions[-1])
    percentage_change = float(((predicted_end_price - last_price) / last_price) * 100.0)
    
    return PredictionResponse(
        symbol=symbol,
        company_name=company_name,
        exchange=exchange,
        is_mocked=is_mocked,
        historical=historical_points,
        predicted=predicted_points,
        last_price=round(last_price, 2),
        predicted_end_price=round(predicted_end_price, 2),
        percentage_change=round(percentage_change, 2)
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
