from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uvicorn
import os

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./nfc_mapping.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class NFCMapping(Base):
    __tablename__ = "mappings"
    uid = Column(String, primary_key=True, index=True)
    url = Column(String, nullable=False)
    name = Column(String, nullable=True) # Description of the card

Base.metadata.create_all(bind=engine)

# Schemas
class MappingCreate(BaseModel):
    uid: str
    url: str
    name: str = None

class MappingResponse(BaseModel):
    uid: str
    url: str
    name: str = None

# App
app = FastAPI(title="NFC URL Mapper")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/map", response_model=MappingResponse)
def create_mapping(mapping: MappingCreate, db: Session = Depends(get_db)):
    db_mapping = db.query(NFCMapping).filter(NFCMapping.uid == mapping.uid).first()
    if db_mapping:
        # Update existing
        db_mapping.url = mapping.url
        db_mapping.name = mapping.name
    else:
        # Create new
        db_mapping = NFCMapping(uid=mapping.uid, url=mapping.url, name=mapping.name)
        db.add(db_mapping)
    
    db.commit()
    db.refresh(db_mapping)
    return db_mapping

@app.get("/scan/{uid}")
def scan_card(uid: str, db: Session = Depends(get_db)):
    """
    Returns the target URL for a given UID.
    """
    mapping = db.query(NFCMapping).filter(NFCMapping.uid == uid).first()
    if not mapping:
        # Default fallback or error
        return {"action": "unknown", "message": "Card not registered"}
    
    return {"action": "open_url", "url": mapping.url}

@app.get("/mappings", response_model=list[MappingResponse])
def list_mappings(db: Session = Depends(get_db)):
    return db.query(NFCMapping).all()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
