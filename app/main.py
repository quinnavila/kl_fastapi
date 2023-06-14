import logging
import uvicorn
from typing import Annotated, Union
from fastapi import Depends, FastAPI, Path
from fastapi.responses import FileResponse

from app.cache import (
    Session, 
    SessionLocal, 
    cache_check, 
    cache_delete_vin, 
    cache_export_database, 
    VinDecoded, 
    Error
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# FastAPI Create Dependency
def get_db():
    """Create a database session and yield it.

    Yields:
        Session: The yielded database session.

    Raises:
        Exception: If an error occurs while creating the session.

    Returns:
        None: The function doesn't return a value directly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

vin_regex = r"^[a-zA-Z0-9]{17}$"
@app.get("/v1/lookup/{vin}", response_model=Union[VinDecoded, Error])
def lookup_vin(
    vin: Annotated[
        str, Path(..., regex=vin_regex, description="17 alphanumeric characters")], 
    db: Session = Depends(get_db)):
    """Lookup VIN information from cache.

    Retrieves decoded VIN information from the cache if available.
    If the VIN is not found in the cache, it is processed and cached.

    Args:
        vin (str): The VIN (Vehicle Identification Number) to look up.
        db (Session): The database session to use.

    Returns:
        Union[VinDecoded, Error]: The decoded VIN information or an error message.

    """
    try:
        vin_decoded = cache_check(vin, db)
        return vin_decoded
    except ValueError as e:
        return Error(error=str(e))

@app.delete("/v1/remove/{vin}")
def delete_vin(
    vin: Annotated[
        str, Path(..., regex=vin_regex, description="17 alphanumeric characters")], 
        db: Session = Depends(get_db)):
    """Delete a VIN record from the cache.

    Deletes a VIN record from the cache based on the provided VIN.

    Args:
        vin (str): The VIN (Vehicle Identification Number) to delete.
        db (Session): The database session to use.

    Returns:
        dict: A message indicating the result of the deletion operation.

    """
    try:
        return cache_delete_vin(vin, db)
    except Exception as e:
        logger.exception("Error occurred deleting VIN: %s", vin)
        return {"error": "An error occurred during VIN deletion." + str(e)}


@app.get("/v1/export")
def export_database(db: Session = Depends(get_db)):
    """Export the VIN cache as a Parquet file.

    Exports the VIN cache as a Parquet file and returns the file as a download response.

    Args:
        db (Session): The database session to use.

    Returns:
        FileResponse: The Parquet file as a download response.

    Raises:
        Exception: Error occurs while exporting the VIN cache.

    """
    try:
        filename = cache_export_database(db)
        return FileResponse(
            filename, 
            media_type="application/octet-stream", 
            filename=filename
            )
    except Exception as e:
        # Handle the exception and return a fallback response
        error_message = "An error occurred while exporting the VIN cache."
        return {"error": error_message + str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)




