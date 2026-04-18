import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_image(file, folder="profio"):
    """
    Save an uploaded image file to Cloudinary.
    Returns the secure URL of the uploaded image.
    """
    try:
        # Read file contents and pass to cloudinary
        response = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image"
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        raise e

def delete_image(url):
    """
    Delete a stored image file from Cloudinary given its URL path.
    """
    if not url or "res.cloudinary.com" not in url:
        return
    
    try:
        # Extract public_id from the URL
        # e.g., https://res.cloudinary.com/cloud_name/image/upload/v1234567890/folder/filename.jpg
        parts = url.split('/')
        # Find the index of "upload", the public_id starts after the version string
        try:
            upload_index = parts.index("upload")
            # Usually the next part is the version (e.g. v12345), so we skip it
            # The remaining parts form the public ID, without the extension
            public_id_with_ext = "/".join(parts[upload_index+2:])
            public_id = os.path.splitext(public_id_with_ext)[0]
            
            cloudinary.uploader.destroy(public_id)
        except ValueError:
            pass
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")
