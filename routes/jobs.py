# routes/jobs.py
# Job posting CRUD and search

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from database.db import get_db
from models.models import Job, User, JobApplication, Notification, NotificationType
from schemas.schemas import JobCreate, JobOut, JobApplicationOut, JobApplicationCreate
from utils.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _build_job_out(job: Job, current_user_id: int) -> dict:
    """Helper to convert Job ORM to JobOut dict with 'applied_by_me'."""
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "company": job.company,
        "location": job.location,
        "job_type": job.job_type,
        "skills": job.skills,
        "role": job.role,
        "salary_range": job.salary_range,
        "poster": job.poster,
        "is_active": job.is_active,
        "created_at": job.created_at,
        "applied_by_me": any(a.applicant_id == current_user_id for a in job.applications),
        "applications_count": len(job.applications),
    }


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new job post. Any authenticated user can post a job."""
    job = Job(**payload.model_dump(), poster_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _build_job_out(job, current_user.id)


@router.get("/", response_model=List[JobOut])
def list_jobs(
    q: Optional[str]     = Query(None, description="Search title, skills, or role"),
    skill: Optional[str] = Query(None),
    role: Optional[str]  = Query(None),
    location: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    skip: int  = 0,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List/search active jobs."""
    query = db.query(Job).options(
        joinedload(Job.poster),
        joinedload(Job.applications)
    ).filter(Job.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            Job.title.ilike(like) | Job.skills.ilike(like) |
            Job.role.ilike(like) | Job.company.ilike(like) |
            Job.location.ilike(like)
        )
    if skill:
        query = query.filter(Job.skills.ilike(f"%{skill}%"))
    if role:
        query = query.filter(Job.role.ilike(f"%{role}%"))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(Job.job_type.ilike(f"%{job_type}%"))

    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    return [_build_job_out(j, current_user.id) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return a single job by ID."""
    job = db.query(Job).options(
        joinedload(Job.poster),
        joinedload(Job.applications)
    ).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _build_job_out(job, current_user.id)


@router.post("/{job_id}/apply", response_model=JobApplicationOut)
def apply_to_job(
    job_id: int,
    payload: JobApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply to a job post with detailed info."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.poster_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot apply to your own job")

    # Check for existing application
    existing = db.query(JobApplication).filter(
        JobApplication.job_id == job_id,
        JobApplication.applicant_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied")

    application = JobApplication(
        job_id=job_id, 
        applicant_id=current_user.id,
        **payload.model_dump()
    )
    db.add(application)

    # Notify poster
    notif = Notification(
        recipient_id=job.poster_id,
        actor_id=current_user.id,
        type=NotificationType.job_application,
        message=f"{current_user.name} applied for your job: {job.title}",
        reference_id=job_id,
    )
    db.add(notif)
    
    db.commit()
    db.refresh(application)
    
    # Reload with applicant details
    return db.query(JobApplication).options(joinedload(JobApplication.applicant)).filter(JobApplication.id == application.id).first()


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a job post (poster only)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.poster_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job post")
    db.delete(job)
    db.commit()
