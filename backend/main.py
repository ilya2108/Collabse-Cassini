import glob
import os
import tempfile
import zipfile
from typing import Any, Dict

import cdsapi
from abc import ABC, abstractmethod

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib import animation


class Location:
    def __init__(self, latitude: float, longitude: float, delta: float = 0.25):
        self.latitude = latitude
        self.longitude = longitude
        self.delta = delta  # Определяет область вокруг точки в градусах

    def get_area(self) -> list:
        """Вычисляет ограничивающий прямоугольник вокруг местоположения."""
        north = self.latitude + self.delta
        south = self.latitude - self.delta
        east = self.longitude + self.delta
        west = self.longitude - self.delta
        return [north, west, south, east]


class DataRequest:
    def __init__(self, dataset_name: str, parameters: dict):
        self.dataset_name = dataset_name
        self.parameters = parameters


class IDataFetcher(ABC):
    @abstractmethod
    def fetch_data(self, data_request: DataRequest):
        pass


class CopernicusDataFetcher(IDataFetcher):
    def __init__(self):
        self.client = cdsapi.Client()

    def fetch_data(self, data_request: DataRequest):
        parameters = data_request.parameters.copy()
        # parameters['area'] = data_request.location.get_area()
        result = self.client.retrieve(
            data_request.dataset_name,
            parameters
        )
        return result


class IPollutantConverter(ABC):
    @abstractmethod
    def convert(self, value: float, pollutant: str) -> float:
        pass


class AtmosphericLayerPollutantConverter(IPollutantConverter):
    def __init__(self, atmospheric_layer_thickness: float = 1000, unit: str = 'μg/m³'):
        if unit == 'kg/m³':
            self.unit_conversion = {
                'no2_conc': 1e12 / atmospheric_layer_thickness,
                'so2_conc': 1e12 / atmospheric_layer_thickness,
                'co_conc': 1e12 / atmospheric_layer_thickness,
                'pm10_conc': 1e12 / atmospheric_layer_thickness,
                'pm2p5_conc': 1e12 / atmospheric_layer_thickness,
                'o3_conc': 1e12 / atmospheric_layer_thickness,
                'nh3_conc': 1e12 / atmospheric_layer_thickness
            }
        elif unit == 'μg/m³':
            self.unit_conversion = {
                'no2_conc': 1,
                'so2_conc': 1,
                'co_conc': 1,
                'pm10_conc': 1,
                'pm2p5_conc': 1,
                'o3_conc': 1,
                'nh3_conc': 1
            }

    def convert(self, value: float, pollutant: str) -> float:
        if pollutant in self.unit_conversion:
            return value * self.unit_conversion[pollutant]
        else:
            raise ValueError(f"Unsupported pollutant: {pollutant}")


class IESGCalculator(ABC):
    @abstractmethod
    def calculate_indicator(self, data: xr.Dataset) -> Dict[str, Any]:
        pass

    @abstractmethod
    def interpret_results(self, esg_results: Dict[str, Any]) -> str:
        pass


class ESGCalculator(IESGCalculator):
    def __init__(self, pollutant_converter: IPollutantConverter):
        self.pollutant_converter = pollutant_converter
        self.who_limits = {
            'no2_conc': 40,  # NO2 (диоксид азота), среднегодовое значение
            'so2_conc': 20,  # SO2 (диоксид серы), среднесуточное значение
            'co_conc': 10000,  # CO (угарный газ), максимальное 8-часовое среднее значение
            'pm10_conc': 20,  # PM10 (частицы размером до 10 мкм), среднегодовое значение
            'pm2p5_conc': 10,  # PM2.5 (частицы размером до 2.5 мкм), среднегодовое значение
            'o3_conc': 100,  # O3 (озон), максимальное 8-часовое среднее значение
            'nh3_conc': 100,
            # NH3 (аммиак), среднегодовое значение (это примерное значение, ВОЗ не устанавливает прямой лимит)
        }

    def calculate_indicator(self, data: xr.Dataset, lat: float, lon: float, delta: float = 0.1) -> Dict[str, Any]:

        # Ограничиваем данные по заданной локации
        lat_idx = abs(data.latitude - lat).argmin()
        lon_idx = abs(data.longitude - lon).argmin()
        data_subset = data.isel(latitude=lat_idx, longitude=lon_idx)

        concentrations = {}
        for pollutant in self.who_limits.keys():
            if pollutant in data:
                if 'latitude' in data_subset[pollutant].dims and 'longitude' in data_subset[pollutant].dims:
                    concentration = data_subset[pollutant].mean(dim=['latitude', 'longitude', 'time'])
                else:
                    concentration = data_subset[pollutant].mean(dim=['time'])
                if 'pressure_level' in concentration.dims:
                    concentration = concentration.mean(dim='pressure_level')
                concentrations[pollutant] = float(self.pollutant_converter.convert(concentration, pollutant))

        normalized_concentrations = {p: concentrations[p] / self.who_limits[p] for p in concentrations}
        pollution_index = np.mean(list(normalized_concentrations.values()))
        pollution_trend = self._calculate_trend(data)

        return {
            'pollution_index': pollution_index,
            'normalized_concentrations': normalized_concentrations,
            'pollution_trend': pollution_trend
        }

    def _calculate_trend(self, data: xr.Dataset) -> Dict[str, float]:
        trends = {}
        for pollutant in self.who_limits.keys():
            if pollutant in data:
                pollutant_data = data[pollutant].mean(dim=['latitude', 'longitude'])
                if 'pressure_level' in pollutant_data.dims:
                    pollutant_data = pollutant_data.mean(dim='pressure_level')
                pollutant_data = self.pollutant_converter.convert(pollutant_data, pollutant)

                time_index = range(len(pollutant_data))
                trend = np.polyfit(time_index, pollutant_data.values, 1)[0]
                trends[pollutant] = float(trend)
        return trends

    def compare_point_to_region(self, data: xr.Dataset, lat: float, lon: float, delta: float = 1) -> str:
        # Ограничиваем данные по заданной локации
        lat_idx = abs(data.latitude - lat).argmin()
        lon_idx = abs(data.longitude - lon).argmin()
        point_data = data.isel(latitude=lat_idx, longitude=lon_idx)

        # Ограничиваем данные по региону вокруг заданной локации
        lat_min, lat_max = lat - delta, lat + delta
        lon_min, lon_max = lon - delta, lon + delta
        data = data.sortby(['latitude', 'longitude'])
        region_data = data.sel(latitude=slice(lat_min, lat_max), longitude=slice(lon_min, lon_max))
        region_data = region_data.mean(dim=['latitude', 'longitude'])

        result = {
            "location": {
                "latitude": lat,
                "longitude": lon
            },
            "region_delta": delta,
            "variables": {}
        }

        for var in point_data.keys():
            if var in self.who_limits:
                point_value = point_data[var].mean().item()
                region_mean = region_data[var].mean().item()
                who_limit = self.who_limits[var]

                percent_difference = ((point_value / region_mean) - 1) * 100 if point_value > region_mean else ((
                                                                                                                            region_mean / point_value) - 1) * 100
                exceeds_who = point_value > who_limit
                who_exceedance_percent = ((point_value / who_limit) - 1) * 100 if exceeds_who else None

                result["variables"][var] = {
                    "point_value": round(point_value, 2),
                    "region_mean": round(region_mean, 2),
                    "who_limit": who_limit,
                    "percent_difference": round(percent_difference, 1),
                    "comparison": "higher" if point_value > region_mean else "lower",
                    "exceeds_who_limit": exceeds_who,
                    "who_exceedance_percent": round(who_exceedance_percent,
                                                    1) if who_exceedance_percent is not None else None
                }

        return result

    def interpret_results(self, esg_results: Dict[str, Any]) -> str:
        interpretation = ""
        if esg_results['pollution_index'] < 0.5:
            interpretation += "The company has a low environmental impact. "
        elif esg_results['pollution_index'] < 1:
            interpretation += "The company has a moderate environmental impact. "
        else:
            interpretation += "The company has a high environmental impact. "

        improving_pollutants = [p for p, t in esg_results['pollution_trend'].items() if t < 0]
        worsening_pollutants = [p for p, t in esg_results['pollution_trend'].items() if t > 0]

        if improving_pollutants:
            interpretation += f"Improvements observed in the following pollutants: {', '.join(improving_pollutants)}. "
        if worsening_pollutants:
            interpretation += f"Deterioration observed in the following pollutants: {', '.join(worsening_pollutants)}. "

        if esg_results['pollution_index'] >= 1:
            interpretation += "It is recommended to develop a plan to reduce emissions. "
        elif worsening_pollutants:
            interpretation += "It is recommended to pay attention to the increasing concentrations of some pollutants. "
        else:
            interpretation += "It is recommended to maintain the current environmental policy and strive for further improvement. "

        return interpretation


class DataVisualizer:
    def visualize(self, data_file: str, output_file: str = 'no2_concentration_paris.gif'):
        # Загрузка данных
        data = xr.open_dataset(data_file)

        # Проверка доступных переменных
        print("Переменные в наборе данных:", list(data.variables))

        # Выбор переменной
        no2 = data['no2']  # Используем фактическое имя переменной

        # Проверка доступных координат
        print("Координаты переменной 'no2':", list(no2.coords))

        # Проверка доступных уровней давления
        print("Доступные уровни давления:", no2.pressure_level.values)

        # Выбор уровня давления
        pressure_level = 500.0  # Измените по необходимости
        if pressure_level not in no2.pressure_level.values:
            raise ValueError(f"Уровень давления {pressure_level} гПа недоступен в данных.")

        # Проверка доступных временных координат
        print("Доступные значения valid_time:", no2.valid_time.values)

        # Создание фигуры и оси
        fig = plt.figure(figsize=(10, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())

        # Фокус на области вокруг Парижа
        ax.set_extent([2.0, 2.7, 48.5, 49.0], crs=ccrs.PlateCarree())

        # Функция для обновления кадров в анимации
        def animate(i):
            ax.clear()
            ax.add_feature(cfeature.COASTLINE)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            ax.set_extent([2.0, 2.7, 48.5, 49.0], crs=ccrs.PlateCarree())

            # Получаем значение времени для текущего кадра
            time_value = no2.valid_time.values[i]
            no2_slice = no2.sel(valid_time=time_value, pressure_level=pressure_level)

            print(f"Кадр {i}, время: {time_value}")
            print("Размерности no2_slice:", no2_slice.dims)
            print("Значения данных:", no2_slice.values)

            # Проверяем, есть ли данные для построения
            if no2_slice.isnull().all():
                print(f"Кадр {i} содержит только NaN значения.")
                return

            im = no2_slice.plot(
                ax=ax,
                transform=ccrs.PlateCarree(),
                cmap='viridis',
                add_colorbar=False
            )

            cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02)
            cbar.set_label('Концентрация NO₂ (μg/m³)')
            time_str = str(time_value)[:16]
            ax.set_title(f'Концентрация NO₂ вокруг Парижа\nУровень давления: {pressure_level} гПа\nВремя: {time_str}')

        # Создание анимации
        anim = animation.FuncAnimation(fig, animate, frames=len(no2.valid_time), interval=500)

        # Сохранение анимации в файл GIF
        anim.save(output_file, writer='pillow')

        plt.show()


class CopernicusDataHandler:
    def __init__(self, zip_file: str):
        self.zip_file = zip_file
        self.temp_dir = tempfile.mkdtemp()
        self.datasets = []

    def extract_and_load_data(self):
        with zipfile.ZipFile(self.zip_file, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)

        # Находим все .nc файлы в распакованной директории
        nc_files = glob.glob(os.path.join(self.temp_dir, '*.nc'))

        if not nc_files:
            print("No NetCDF files found in the extracted data.")
            return

        # Загружаем каждый .nc файл
        for file in nc_files:
            dataset = xr.open_dataset(file)
            self.datasets.append(dataset)
            print(f"Variables in {os.path.basename(file)}:", list(dataset.variables))

    def get_combined_data(self):
        if not self.datasets:
            print("No datasets loaded.")
            return None

        # Объединяем все датасеты
        combined_data = xr.merge(self.datasets)
        return combined_data

    def close_data(self):
        for dataset in self.datasets:
            dataset.close()
        self.datasets.clear()

    def __del__(self):
        self.close_data()
        # Очистка временных файлов
        # for file in os.listdir(self.temp_dir):
        #     try:
        #         os.remove(os.path.join(self.temp_dir, file))
        #     except PermissionError:
        #         print(f"Could not remove file: {file}")
        # try:
        #     os.rmdir(self.temp_dir)
        # except PermissionError:
        #     print(f"Could not remove temporary directory: {self.temp_dir}")


class IVisualizer(ABC):
    @abstractmethod
    def visualize(self, data: xr.Dataset) -> None:
        pass


class ESGVisualizer(IVisualizer):
    def __init__(self, pollutant_converter: IPollutantConverter, company_location: Location):
        self.pollutant_converter = pollutant_converter
        self.company_location = company_location
        self.who_limits = {
            'no2_conc': 40,  # NO2 (диоксид азота), среднегодовое значение
            'so2_conc': 20,  # SO2 (диоксид серы), среднесуточное значение
            'co_conc': 10000,  # CO (угарный газ), максимальное 8-часовое среднее значение
            'pm10_conc': 20,  # PM10 (частицы размером до 10 мкм), среднегодовое значение
            'pm2p5_conc': 10,  # PM2.5 (частицы размером до 2.5 мкм), среднегодовое значение
            'o3_conc': 100,  # O3 (озон), максимальное 8-часовое среднее значение
            'nh3_conc': 100,
            # NH3 (аммиак), среднегодовое значение (это примерное значение, ВОЗ не устанавливает прямой лимит)
        }

    def visualize(self, data: xr.Dataset, lat: float, lon: float, delta: float = 0.1) -> None:
        self.plot_pollutant_dynamics(data, lat, lon, delta)
        # self.plot_who_comparison(data)
        # self.plot_heatmaps(data)

    def plot_pollutant_dynamics(self, data: xr.Dataset, lat: float, lon: float, delta: float = 0.1,
                                output_file: str = 'pollutant_dynamics.png') -> None:
        # Ограничиваем данные по заданной локации
        lat_idx = abs(data.latitude - lat).argmin()
        lon_idx = abs(data.longitude - lon).argmin()
        data_subset = data.isel(latitude=lat_idx, longitude=lon_idx)

        pollutants = [var for var in data_subset.variables if var in self.who_limits]
        fig, axes = plt.subplots(len(pollutants), 1, figsize=(20, 6 * len(pollutants)))
        if len(pollutants) == 1:
            axes = [axes]

        for i, pollutant in enumerate(pollutants):
            if 'latitude' in data_subset.dims and 'longitude' in data_subset.dims:
                data_series = data_subset[pollutant].mean(dim=['latitude', 'longitude'])
            else:
                data_series = data_subset[pollutant]
            if 'pressure_level' in data_series.dims:
                data_series = data_series.mean(dim='pressure_level')
            data_series = self.pollutant_converter.convert(data_series, pollutant)

            if np.isnan(data_series.values).all():
                print(f"Warning: All values for {pollutant} are NaN. Skipping this pollutant.")
                continue

            data_series.plot(ax=axes[i], x='time')
            axes[i].axhline(y=self.who_limits[pollutant], color='r', linestyle='--', label='WHO Limit')
            axes[i].set_title(
                f'{pollutant.upper()} Average Concentration Over Time\nLocation: {lat:.2f}°N, {lon:.2f}°E (±{delta:.2f}°)')
            axes[i].set_ylabel('Concentration (μg/m³)')
            axes[i].legend()

        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()

    def plot_who_comparison(self, data: xr.Dataset, output_file: str = 'who_comparison.png') -> None:
        pollutants = [var for var in data.variables if var in self.who_limits]
        fig, ax = plt.subplots(figsize=(12, 6))

        avg_concentrations = []
        for pollutant in pollutants:
            data_avg = data[pollutant].mean(dim=['latitude', 'longitude', 'time'])
            if 'pressure_level' in data_avg.dims:
                data_avg = data_avg.mean(dim='pressure_level')
            data_avg = self.pollutant_converter.convert(data_avg, pollutant)

            if np.isnan(data_avg.values).all():
                print(f"Warning: All values for {pollutant} are NaN. Skipping this pollutant.")
                avg_concentrations.append(0)
            else:
                avg_concentrations.append(data_avg.values)

        x = range(len(pollutants))
        ax.bar(x, avg_concentrations, align='center', alpha=0.8, label='Average Concentration')
        ax.bar(x, [self.who_limits[p] for p in pollutants], align='center', alpha=0.5, label='WHO Limit')

        ax.set_ylabel('Concentration (μg/m³)')
        ax.set_title('Average Pollutant Concentrations vs WHO Limits')
        ax.set_xticks(x)
        ax.set_xticklabels(pollutants)
        ax.legend()

        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()

    def plot_heatmaps(self, data: xr.Dataset, output_file: str = 'pollution_heatmaps.png') -> None:
        pollutants = [var for var in data.variables if var in self.who_limits]
        fig, axes = plt.subplots(len(pollutants), 1, figsize=(20, 10 * len(pollutants)),
                                 subplot_kw={'projection': ccrs.PlateCarree()})
        if len(pollutants) == 1:
            axes = [axes]

        for i, pollutant in enumerate(pollutants):
            data_subset = data[pollutant]
            if 'pressure_level' in data_subset.dims:
                data_subset = data_subset.mean(dim='pressure_level')
            data_subset = data_subset.mean(dim='time')
            data_subset = self.pollutant_converter.convert(data_subset, pollutant)

            if np.isnan(data_subset.values).all():
                print(f"Warning: All values for {pollutant} are NaN. Skipping this pollutant.")
                continue

            im = data_subset.plot(
                ax=axes[i],
                transform=ccrs.PlateCarree(),
                cmap='viridis',
                add_colorbar=False
            )

            axes[i].set_global()
            axes[i].coastlines()
            axes[i].add_feature(cfeature.BORDERS, linestyle=':')

            company_marker = plt.Circle((self.company_location.longitude, self.company_location.latitude),
                                        radius=0.1, color='red', transform=ccrs.PlateCarree())
            axes[i].add_artist(company_marker)

            plt.colorbar(im, ax=axes[i], orientation='vertical', pad=0.05,
                         label=f'{pollutant.upper()} Concentration (μg/m³)')
            axes[i].set_title(f'{pollutant.upper()} Heatmap')

        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()


if __name__ == "__main__":
    # Задаем местоположение (например, Париж)
    location = Location(latitude=48.8566, longitude=2.3522, delta=0.1)

    # Параметры запроса данных для CAMS European air quality reanalyses
    parameters = {
        'variable': [
            'ammonia',  # NH3
            'carbon_monoxide',  # CO
            'nitrogen_dioxide',  # NO2
            'ozone',  # O3
            'particulate_matter_2.5um',  # PM2.5
            'particulate_matter_10um',  # PM10
            'sulphur_dioxide',  # SO2
            'non_methane_vocs',  # NMVOC (важный предшественник озона)
            'dust',  # может быть важным компонентом PM
            'formaldehyde',  # HCHO (важный индикатор загрязнения)
            'nitrogen_monoxide',  # NO (важен для понимания цикла NO2)
            'pm2.5_total_organic_matter',  # органическая составляющая PM2.5
            'pm10_wildfires',  # вклад пожаров в PM10
            'secondary_inorganic_aerosol'  # важный компонент PM
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

    # # Создаем загрузчик данных и получаем данные
    data_fetcher = CopernicusDataFetcher()
    # result = data_fetcher.fetch_data(data_request)

    # Загружаем данные
    zip_file = '../copernicus_data.zip'
    # result.download(zip_file)

    # Обрабатываем данные
    data_handler = CopernicusDataHandler(zip_file)
    data_handler.extract_and_load_data()
    combined_data = data_handler.get_combined_data()

    pollutant_converter = AtmosphericLayerPollutantConverter()

    # Создаем визуализатор и генерируем все графики
    visualizer = ESGVisualizer(pollutant_converter=pollutant_converter, company_location=location)
    visualizer.visualize(data=combined_data, lat=location.latitude, lon=location.longitude, delta=location.delta)

    # Закрываем файлы данных
    data_handler.close_data()

    calculator = ESGCalculator(pollutant_converter=pollutant_converter)
    esg_results = calculator.calculate_indicator(combined_data, lat=location.latitude, lon=location.longitude,
                                                 delta=location.delta)
    print(esg_results)
    interpretation = calculator.interpret_results(esg_results)
    print(interpretation)
    compare = calculator.compare_point_to_region(combined_data, lat=location.latitude, lon=location.longitude)
    print(compare)
