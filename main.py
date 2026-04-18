import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
from dotenv import load_dotenv
from database.db import Base, engine
import models.models  
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.posts import router as posts_router
from routes.jobs import router as jobs_router
from routes.connections import router as connections_router
from routes.messages import router as messages_router
from routes.notifications import router as notifications_router

load_dotenv()

Base.metadata.create_all(bind=engine)



app = FastAPI(
    title="Profio API",
    description="Professional social networking platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




app.include_router(auth_router)
app.include_router(users_router)
app.include_router(posts_router)
app.include_router(jobs_router)
app.include_router(connections_router)
app.include_router(messages_router)
app.include_router(notifications_router)

@app.get("/")
def health():
    return {"status": "ok"}