from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from typing import Dict, Any

from main import AtmosphericLayerPollutantConverter, CopernicusDataFetcher, CopernicusDataHandler, ESGCalculator

app = FastAPI()


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    delta: float = Field(0.1, ge=0)


class AIRQualityData(BaseModel):
    pollution_index: float
    normalized_concentrations: Dict[str, float]
    pollution_trend: Dict[str, float]


class DataRequest(BaseModel):
    dataset_name: str
    parameters: Dict[str, Any]


# Global variables
combined_data = None
pollutant_converter = AtmosphericLayerPollutantConverter()
calculator = ESGCalculator(pollutant_converter)


def load_data():
    global combined_data

    parameters = {
        'variable': [
            'ammonia', 'carbon_monoxide', 'nitrogen_dioxide', 'ozone',
            'particulate_matter_2.5um', 'particulate_matter_10um', 'sulphur_dioxide',
            'non_methane_vocs', 'dust', 'formaldehyde', 'nitrogen_monoxide',
            'pm2.5_total_organic_matter', 'pm10_wildfires', 'secondary_inorganic_aerosol'
        ],
        'model': ['ensemble'],
        'level': ['0'],
        'date': ['2024-08-01/2024-08-20'],
        'type': ['forecast'],
        'time': ['00:00'],
        'leadtime_hour': ['0'],
        'data_format': 'netcdf_zip'
    }

    data_request = DataRequest(
        dataset_name='cams-europe-air-quality-forecasts',
        parameters=parameters,
    )

    data_fetcher = CopernicusDataFetcher()
    result = data_fetcher.fetch_data(data_request)

    zip_file = '../copernicus_data.zip'
    result.download(zip_file)

    data_handler = CopernicusDataHandler(zip_file)
    data_handler.extract_and_load_data()
    combined_data = data_handler.get_combined_data()


@app.on_event("startup")
async def startup_event():
    background_tasks = BackgroundTasks()
    background_tasks.add_task(load_data)
    await background_tasks()


@app.post("/esg_results", response_model=AIRQualityData)
async def get_esg_results(location: Location):
    global combined_data, calculator

    print(combined_data)
    if combined_data is None:
        raise HTTPException(status_code=503, detail="Data not loaded yet. Please try again later.")

    esg_results = calculator.calculate_indicator(combined_data, lat=location.latitude, lon=location.longitude,
                                                 delta=location.delta)
    return AIRQualityData(**esg_results)


@app.post("/interpretation")
async def get_interpretation(location: Location):
    global combined_data, calculator
    if combined_data is None:
        raise HTTPException(status_code=503, detail="Data not loaded yet. Please try again later.")

    esg_results = calculator.calculate_indicator(combined_data, lat=location.latitude, lon=location.longitude,
                                                 delta=location.delta)
    interpretation = calculator.interpret_results(esg_results)
    return {"interpretation": interpretation}


@app.post("/comparison")
async def get_comparison(location: Location):
    global combined_data, calculator
    if combined_data is None:
        raise HTTPException(status_code=503, detail="Data not loaded yet. Please try again later.")

    compare = calculator.compare_point_to_region(combined_data, lat=location.latitude, lon=location.longitude)
    return {"comparison": compare}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
