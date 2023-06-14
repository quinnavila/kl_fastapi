import os
import pytest
import requests
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.cache import (
    process_vin, 
    get_external_api, 
    cache_vin,
    cache_delete_vin,
    cache_export_database,
    cache_check, 
    VinCache, 
    VinDecoded, 
    Error, 
    Base,
)

# TODO: Needs models tests
# TODO: Add concurrency tests

@pytest.fixture(scope="function", autouse=True)
def db_session():
    """Create a database session and yield it.

    Yields:
        Session: The yielded database session.

    Raises:
        Exception: If an error occurs while creating the session.

    Returns:
        None: The function doesn't return a value directly.
    """
    engine = create_engine(
        'sqlite+pysqlite:///file:test_vin_cache?mode=memory&cache=shared&uri=true', 
        echo=True)
    SessionLocal = sessionmaker(bind=engine)


    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up the database after each test
        Base.metadata.drop_all(bind=engine)
        db.close()


def test_cache_vin(db_session: Session):
    vin = "1XPWD40X1ED215307"
    decoded_data = VinDecoded(
        vin=vin,
        make="MakeValue",
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue",
        cached=False
    )

    cache_vin(db_session, vin, decoded_data)

    result = db_session.query(VinCache).filter_by(vin=vin).first()

    assert result is not None
    assert result.vin == vin
    assert result.make == decoded_data.make
    assert result.model == decoded_data.model
    assert result.model_year == decoded_data.model_year
    assert result.body_class == decoded_data.body_class
    assert result.cached is True

    db_session.delete(result)
    db_session.commit()

def test_cache_delete_vin(db_session: Session):
    vin = "1XPWD40X1ED215307"
    decoded_data = VinDecoded(
        vin=vin,
        make="MakeValue",
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue",
        cached=False
    )

    cache_vin(db_session, vin, decoded_data)
    result = cache_delete_vin(vin, db_session)
    deleted_record = db_session.query(VinCache).filter_by(vin=vin).first()

    assert result["message"] == f"Successfully removed VIN: {vin}."
    assert deleted_record is None

@pytest.fixture
def mock_db_query(mocker):
    return mocker.patch("app.cache.Session.query")

@pytest.fixture
def mock_process_vin(mocker):
    return mocker.patch("app.cache.process_vin")

def test_cache_check(mock_process_vin, db_session: Session):
    vin = "1XPWD40X1ED215307"
    decoded_data = VinDecoded(
        vin=vin,
        make="MakeValue",
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue",
        cached=True
    )
    
    mock_process_vin.return_value = decoded_data

    result = cache_check(vin, db_session)

    expected_result = VinDecoded(
        vin=vin,
        make="MakeValue",
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue",
        cached=True
    )
    assert result == expected_result
    assert result.cached

def test_cache_check_cached(mock_db_query, db_session):
    vin = "1XPWD40X1ED215307"
    cached_record = VinCache(
        vin=vin,
        make="MakeValue",
        model="ModelValue", 
        model_year="2023",
        body_class="BodyClassValue",
        cached=True
    )
    mock_db_query.return_value.filter_by.return_value.first.return_value = cached_record

    result = cache_check(vin, db_session)

    expected_result = VinDecoded(
        vin=vin, 
        make="MakeValue", 
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue", 
        cached=True)
    assert result == expected_result

def test_cache_check_not_cached(mock_db_query, mock_process_vin, db_session):
    vin = "1XPWD40X1ED215307"
    mock_db_query.return_value.filter_by.return_value.first.return_value = None

    mock_process_vin.return_value = VinDecoded(
        vin=vin, 
        make="MakeValue", 
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue", 
        cached=False)

    result = cache_check(vin, db_session)

    expected_result = VinDecoded(
        vin=vin, 
        make="MakeValue", 
        model="ModelValue", 
        model_year="2023",
        body_class="BodyClassValue", 
        cached=False)
    assert result == expected_result
    

def test_cache_check_value_error(mock_db_query, mock_process_vin, db_session):
    vin = "INVALIDVIN"
    mock_db_query.return_value.filter_by.return_value.first.return_value = None

    mock_process_vin.side_effect = ValueError("Invalid VIN")

    result = cache_check(vin, db_session)

    expected_result = Error(error="Invalid VIN")
    assert result == expected_result


def test_cache_export_database(db_session: Session):
    vin = "1XPWD40X1ED215307"
    decoded_data = VinDecoded(
        vin=vin,
        make="MakeValue",
        model="ModelValue",
        model_year="2023",
        body_class="BodyClassValue",
        cached=False
    )

    cache_vin(db_session, vin, decoded_data)
    export_filename = cache_export_database(db_session)
    assert export_filename == "vin_cache.parquet"
    df = pd.read_parquet(export_filename)

    assert len(df) == 1 
    assert df["vin"].iloc[0] == vin 

    os.remove(export_filename)


@pytest.fixture
def mock_get_external_api(mocker):
    return mocker.patch("app.cache.get_external_api")

@pytest.mark.parametrize(
    "vin, expected_result",
    [
        ("1XPWD40X1ED215307", {
            "vin": "1XPWD40X1ED215307",
            "make": "MakeValue",
            "model": "ModelValue",
            "model_year": "2023",
            "body_class": "BodyClassValue",
            "cached": False
        }),
        ("INVALIDVIN", {"error": "Invalid VIN data"})
    ]
)
def test_process_vin(mock_get_external_api, vin, expected_result):
    mock_get_external_api.return_value = expected_result

    try:
        result = process_vin(vin)
    except ValueError as e:
        assert str(e) == "Invalid VIN data"
    else:
        mock_get_external_api.assert_called_once_with(vin)
        assert result.dict() == expected_result


@pytest.fixture
def mock_requests_get(mocker):
    return mocker.patch.object(requests, 'get')

def test_get_external_api(mock_requests_get):
    # Set up the mock response
    mock_response = mock_requests_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Results": [
            {
                "Make": "MakeValue",
                "Model": "ModelValue",
                "ModelYear": "2023",
                "BodyClass": "BodyClassValue"
            }
        ]
    }

    vin = "1XPWD40X1ED215307"
    result = get_external_api(vin)

    expected_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json&modelyear="
    mock_requests_get.assert_called_once_with(expected_url)

    expected_result = {
        "Results": [
            {
                "Make": "MakeValue",
                "Model": "ModelValue",
                "ModelYear": "2023",
                "BodyClass": "BodyClassValue"
            }
        ]
    }
    assert result == expected_result