import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.cache import (
    VinDecoded,
)

client = TestClient(app)


@pytest.fixture
def mock_cache_check(mocker):
    return mocker.patch("app.main.cache_check", return_value=VinDecoded(
        vin="1XPWD40X1ED215307",
        make="MakeValue",
        model="ModelValue",
        model_year="2022",
        body_class="BodyClassValue",
        cached=False
    ))


@pytest.mark.parametrize(
    "vin, expected_status_code, expected_response",
    [
        ("1XPWD40X1ED215307", 200, {
            "vin": "1XPWD40X1ED215307",
            "make": "MakeValue",
            "model": "ModelValue",
            "model_year": "2022",
            "body_class": "BodyClassValue",
            "cached": False
        }),
        ("", 404, {
            "detail": "Not Found"
        }),
        ("INVALIDVIN", 422, {
            "detail": [
                {
                    "loc": [
                        "path",
                        "vin"
                        ],
                        "msg":"string does not match regex \"^[a-zA-Z0-9]{17}$\"",
                        "type":"value_error.str.regex",
                        "ctx":{"pattern":"^[a-zA-Z0-9]{17}$"}
                        }
            ]
        }),
    ],
)
def test_lookup_vin(mock_cache_check, vin, expected_status_code, expected_response):
    response = client.get(f"/v1/lookup/{vin}")
    assert response.status_code == expected_status_code
    assert response.json() == expected_response

@pytest.fixture
def mock_cache_delete_vin(mocker):
    vin = "1XPWD40X1ED215307"
    return mocker.patch(
        "app.main.cache_delete_vin", 
        return_value={"message": f"Successfully removed VIN: {vin}."})


def test_delete_vin(mock_cache_delete_vin):
    vin = "1XPWD40X1ED215307"
    response = client.delete(f"/v1/remove/{vin}")
    assert response.status_code == 200
    assert response.json() == {"message": f"Successfully removed VIN: {vin}."}

@pytest.fixture
def mock_cache_export_database(mocker):
    return mocker.patch(
        "app.cache.cache_export_database", 
        return_value="/path/to/exported_file.parquet")

def test_export_database(mock_cache_export_database):
    response = client.get("/v1/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith('attachment; filename=')

    filename = response.headers["content-disposition"].split("filename=")[1]
    filename = filename.strip('"')  # Remove surrounding quotes
    assert os.path.isfile(filename)

    os.remove(filename)