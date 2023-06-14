from typing import Dict, Any, Union
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sqlalchemy import create_engine, Column, String, Boolean, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, constr
import logging

logger = logging.getLogger(__name__)

engine = create_engine('sqlite+pysqlite:///file:vin_cache?mode=memory&cache=shared&uri=true')
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class VinCache(Base):
    __tablename__ = 'vins'

    vin = Column(String, primary_key=True)
    make = Column(String)
    model = Column(String)
    model_year = Column(String)
    body_class = Column(String)
    cached = Column(Boolean)

    def to_dict(self):
        return {
            'vin': self.vin,
            'make': self.make,
            'model': self.model,
            'model_year': self.model_year,
            'body_class': self.body_class
        }

class VinDecoded(BaseModel):
    vin: constr(regex="^[a-zA-Z0-9]{17}$")
    make: str
    model: str
    model_year: str
    body_class: str
    cached: bool

class Error(BaseModel):
    error: str

Base.metadata.create_all(bind=engine)

URL = 'https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues'

def cache_check(vin: str, db: Session) -> VinDecoded:
    """Checks if the VIN is present in the cache.

     Args:
        vin (str): VIN.
        db (Session): database session to use.

    Returns:
        Union[VinDecoded, Error]: If the VIN is in the cache returns `VinDecoded`
                                  If the VIN is not found vin_process looks it up, 
                                  If an error occurs returns `Error`

    Raises:
        ValueError: If errors decoding the VIN (raised by `process_vin`).
    """
    result = db.query(VinCache).filter_by(vin=vin).first()

    if result:
        logger.info("Returning from cache")
        decoded_data = VinDecoded(
            vin=result.vin,
            make=result.make,
            model=result.model,
            model_year=result.model_year,
            body_class=result.body_class,
            cached=True
        )
        return decoded_data
    else:
        logger.info("Cache miss lookup")
        try:
            vin_decoded = process_vin(vin)
            logger.info("Writing to DB")
            cache_vin(db, vin, vin_decoded)
            return vin_decoded
        except ValueError as e:
            # Handle the case when an error occurs while decoding the VIN
            logger.error("Error while decoding the VIN: %s", str(e))
            return Error(error=str(e))

def cache_vin(db: Session, vin: str, decoded_data: VinDecoded) -> None:
    """Caches the decoded VIN information.

    Args:
        db (Session): Session to use.
        vin (str): vin into cache.
        decoded_data (VinDecoded): The decoded VIN information to cache.

    Returns:
        None

    Raises:
        SQLAlchemyError: If errors during the database transaction.
    """
    vin_cache = VinCache(
        vin=vin,
        make=decoded_data.make,
        model=decoded_data.model,
        model_year=decoded_data.model_year,
        body_class=decoded_data.body_class,
        cached=True
    )
    try:
        db.add(vin_cache)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database transaction failed")
        raise SQLAlchemyError("Database transaction failed") from e

def cache_delete_vin(vin: str, db: Session) -> dict:
    """Deletes the VIN record from the cache.

    Args:
        vin (str): VIN to delete.
        db (Session): Database session to use.

    Returns:
        dict: Deletion result message.
    """
    
    try:
        delete_statement = delete(VinCache).where(VinCache.vin == vin)
        result = db.execute(delete_statement)
        db.commit()

        if result.rowcount == 0:
            logger.info("No record found with VIN: %s. No deletion performed.", vin)
            return {"message": f"No record found with VIN: {vin}. No deletion."}
        else:
            logger.info("Successfully removed VIN: %s.", vin)
            return {"message": f"Successfully removed VIN: {vin}."}

    except SQLAlchemyError as e:
        logger.exception("Error occurred deleting VIN: %s", vin)
        db.rollback()
        return {"error": "Failed to delete VIN from cache.", "exception": str(e)}

def cache_export_database(db: Session) -> str:
    """Exports the VIN cache database to a Parquet file.

    Args:
        db (Session): Database session.

    Returns:
        str: Filename of the exported Parquet file.

    Raises:
        SQLAlchemyError: If errors during the database query or export process.
    """
    results = db.query(VinCache).all()
    data = [result.to_dict() for result in results]

    # Todo: Need to review probably can remove pandas using pyarrow.
    df = pd.DataFrame(data)

    table = pa.Table.from_pandas(df)

    filename = "vin_cache.parquet"
    pq.write_table(table, filename)

    return filename

def process_vin(vin) -> Union[VinDecoded, Error]:
    """Processes a VIN and returns the decoded information.

    Args:
        vin (str): VIN to process.

    Returns:
        Union[VinDecoded, Error]:returns VIN information as `VinDecoded` object.
                                 If an error occurs, returns an `Error` object.

    Raises:
        ValueError: If error message from the external API.
                    If needed keys are not present or the index is out of range.
    """
    vin_decoded_json = get_external_api(vin)
    if "error" in vin_decoded_json:
        raise ValueError(vin_decoded_json["error"])
    try:
        result = vin_decoded_json['Results'][0]
        vin_decoded = VinDecoded(
            vin=vin,
            make=result['Make'],
            model=result['Model'],
            model_year=result['ModelYear'],
            body_class=result['BodyClass'],
            cached = False
        )
        return vin_decoded
    except (KeyError, IndexError) as e:
        raise ValueError("Invalid VIN data") from e   

def get_external_api(vin, url=URL, format="json", modelyear="") -> Dict[str, Any]:
    """Calls an external API to retrieve information for a given VIN.

    Args:
        vin (str): VIN to retrieve.
        url (str, optional): URL of the external API. Defaults to URL.
        format (str, optional): Format of the response. Defaults to "json".
        modelyear (str, optional): The model year defaults to "".

    Returns:
        Dict[str, Any]: Data from the API as dict.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
        Exception: If an unexpected error occurs.
    """
    try:
        r = requests.get(f"{url}/{vin}?format={format}&modelyear={modelyear}")
        r.raise_for_status() 
        json_data = r.json()
        return json_data
    except requests.exceptions.RequestException as e:
        # Handle any request-related errors
        print("An error occurred during the request:", str(e))
        return {"error": "An error occurred during the request: " + str(e)}
    except Exception as e:
        # Handle any other exceptions
        print("An unexpected error occurred:", str(e))
        return {"error": "An unexpected error occurred: " + str(e)}


