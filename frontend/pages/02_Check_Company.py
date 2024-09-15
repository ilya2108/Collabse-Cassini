"""
# Check Company
Analyze ESG data for a specific company.
"""

import streamlit as st
from static import *
import pandas as pd
from geopy.geocoders import Nominatim
import ssl
import certifi
import requests
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Check Company",
    page_icon="🏢",
    layout="wide",
)

def get_elevation(lat, lon):
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['results'][0]['elevation']
    else:
        return None


def process_address(address):
    if address:
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        geolocator = Nominatim(user_agent="streamlit_app", ssl_context=ctx)
        location = geolocator.geocode(address)

        if location:
            elevation = get_elevation(location.latitude, location.longitude)
            df = pd.DataFrame({
                'lat': [location.latitude],
                'lon': [location.longitude]
            })
            return {
                "map_data": df,
                "elevation": elevation
            }
        else:
            st.error("Address not found. Please enter a valid address.")
            return None


def visualize_esg_data(esg_results, interpretation, comparison):
    st.header("ESG Data Visualization")

    # Pollution Index
    st.subheader("Pollution Index")
    pollution_index = esg_results["pollution_index"]
    st.metric("", f"{pollution_index:.2%}", label_visibility="hidden")

    # Normalized Concentrations
    st.subheader("Normalized Concentrations")
    norm_conc = pd.DataFrame(esg_results["normalized_concentrations"].items(), columns=['Pollutant', 'Concentration'])
    fig_norm_conc = px.bar(norm_conc, x='Pollutant', y='Concentration', title="")
    st.plotly_chart(fig_norm_conc)

    # Pollution Trend
    st.subheader("Pollution Trend")
    pollution_trend = pd.DataFrame(esg_results["pollution_trend"].items(), columns=['Pollutant', 'Trend'])
    fig_trend = px.line(pollution_trend, x='Pollutant', y='Trend', title="")
    st.plotly_chart(fig_trend)

    # Interpretation
    st.subheader("Interpretation")
    st.write(interpretation["interpretation"])

    # Comparison
    st.subheader("Pollutant Comparison (Log Scale)")
    comparison_data = []
    for pollutant, values in comparison["comparison"]["variables"].items():
        comparison_data.append({
            "Pollutant": pollutant.replace("_conc", "").upper(),
            "Point Value": values["point_value"],
            "Region Mean": values["region_mean"],
            "WHO Limit": values["who_limit"]
        })
    comparison_df = pd.DataFrame(comparison_data)

    fig_comparison = go.Figure()
    for column in ["Point Value", "Region Mean", "WHO Limit"]:
        fig_comparison.add_trace(go.Bar(x=comparison_df["Pollutant"], y=comparison_df[column], name=column))
    fig_comparison.update_layout(
        barmode='group',
        title="Pollutant Comparison (Log Scale)",
        yaxis_type="log",  # Устанавливаем логарифмическую шкалу для оси Y
        yaxis_title="Concentration (log scale)"
    )
    st.plotly_chart(fig_comparison)

    # WHO Limit Exceedance
    st.subheader("WHO Limit Exceedance")
    for pollutant, values in comparison["comparison"]["variables"].items():
        if values["exceeds_who_limit"]:
            st.warning(
                f"{pollutant.replace('_conc', '').upper()} exceeds WHO limit by {values['who_exceedance_percent']:.2f}%")
        else:
            st.success(f"{pollutant.replace('_conc', '').upper()} is within WHO limit")


st.title("Add a Company")
st.write("Please enter the company details to start the data collection and ESG score generation.")
address_data = {}

with st.form(key='company_form'):
    company_name = st.text_input("Company Name")
    location = st.text_input("Location (Country)")
    company_size = st.selectbox("Company Size", company_sizes_list)
    industry = st.selectbox(
        "Operations Area",
        industries_list
    )
    address = st.text_input("Address")
    if address:
        address_data = process_address(address)
        if address_data:
            st.map(address_data["map_data"])
    submit_button = st.form_submit_button(label='Submit')

if submit_button:
    company_data = {
        'Company Name': company_name,
        'Location': location,
        'Company Size': company_size,
        'Industry': industry,
    }

    if address_data:
        df = address_data["map_data"]
        values = df[['lat', 'lon']].values[0]
        lat, lon = values
        api_data = {
            "latitude": lat,
            "longitude": lon,
            "delta": 0.1
        }

        api_endpoints = {
            'esg_results': 'http://35.228.76.200:8000/esg_results',
            'interpretation': 'http://35.228.76.200:8000/interpretation',
            'comparison': 'http://35.228.76.200:8000/comparison'
        }
        api_responses = {}

        for key, url in api_endpoints.items():
            try:
                response = requests.post(url, json=api_data)
                response.raise_for_status()
                api_responses[key] = response.json()
                st.success(f"Successfully retrieved {key.replace('_', ' ').title()}.")
            except requests.exceptions.HTTPError as http_err:
                st.error(f"HTTP error occurred for {key}: {http_err}")
            except Exception as err:
                st.error(f"An error occurred for {key}: {err}")

        if all(key in api_responses for key in api_endpoints.keys()):
            visualize_esg_data(api_responses['esg_results'], api_responses['interpretation'],
                               api_responses['comparison'])
        else:
            st.error("Unable to visualize data due to missing API responses.")
    else:
        st.error("Please provide a valid address to generate ESG data.")