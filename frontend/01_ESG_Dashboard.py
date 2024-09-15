"""
# ESG Dashboard
This page shows an overview of ESG data for multiple companies.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import os

# Set page config
st.set_page_config(
    page_title="ESG Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Function to fetch data from API and save it
def fetch_and_save_data():
    api_endpoints = {
        'esg_results': 'http://35.228.76.200:8000/esg_results',
        'interpretation': 'http://35.228.76.200:8000/interpretation',
        'comparison': 'http://35.228.76.200:8000/comparison'
    }

    companies = [
        {"name": "TechInnovate", "latitude": 51.5074, "longitude": -0.1278, "size": "Large", "industry": "Technology"},
        {"name": "EcoSolutions", "latitude": 48.8566, "longitude": 2.3522, "size": "Medium",
         "industry": "Environmental"},
        {"name": "GreenEnergy", "latitude": 52.5200, "longitude": 13.4050, "size": "Large", "industry": "Energy"},
        {"name": "BioInnovate", "latitude": 41.9028, "longitude": 12.4964, "size": "Small",
         "industry": "Biotechnology"},
        {"name": "SmartManufacturing", "latitude": 59.3293, "longitude": 18.0686, "size": "Large",
         "industry": "Manufacturing"},
        {"name": "CleanWaterTech", "latitude": 52.3676, "longitude": 4.9041, "size": "Medium",
         "industry": "Water Treatment"},
        {"name": "SustainableFashion", "latitude": 55.6761, "longitude": 12.5683, "size": "Small",
         "industry": "Retail"},
        {"name": "GreenTransport", "latitude": 48.2082, "longitude": 16.3738, "size": "Medium",
         "industry": "Transportation"},
        {"name": "EcoAgriculture", "latitude": 50.8503, "longitude": 4.3517, "size": "Large",
         "industry": "Agriculture"},
        {"name": "RenewableMaterials", "latitude": 45.4642, "longitude": 9.1900, "size": "Small",
         "industry": "Materials"},
        {"name": "CircularEconomy", "latitude": 40.4168, "longitude": -3.7038, "size": "Medium",
         "industry": "Recycling"},
        {"name": "EfficientBuildings", "latitude": 52.2297, "longitude": 21.0122, "size": "Large",
         "industry": "Construction"},
        {"name": "SustainableFinance", "latitude": 47.3769, "longitude": 8.5417, "size": "Large",
         "industry": "Finance"},
        {"name": "EcoTourism", "latitude": 38.7223, "longitude": -9.1393, "size": "Small", "industry": "Tourism"},
        {"name": "HealthTech", "latitude": 55.7558, "longitude": 37.6173, "size": "Medium", "industry": "Healthcare"}
    ]

    all_data = []

    for company in companies:
        company_data = {
            "Company Name": company["name"],
            "Size": company["size"],
            "Industry": company["industry"]
        }
        api_data = {
            "latitude": company["latitude"],
            "longitude": company["longitude"],
            "delta": 0.1
        }

        for key, url in api_endpoints.items():
            try:
                response = requests.post(url, json=api_data)
                response.raise_for_status()
                company_data[key] = response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data for {company['name']}: {e}")
                break

        if len(company_data) == 6:  # If we successfully got all 3 API responses + name, size, industry
            all_data.append(company_data)

    # Save data to file
    with open('esg_data.json', 'w') as f:
        json.dump(all_data, f)

    return all_data


# Function to load data from file or fetch if file doesn't exist
def get_data():
    if os.path.exists('esg_data.json'):
        with open('esg_data.json', 'r') as f:
            return json.load(f)
    else:
        return fetch_and_save_data()


# Load data
data = get_data()

# Process data for dashboard
df = pd.DataFrame([
    {
        'Company Name': item['Company Name'],
        'Pollution Index': item['esg_results']['pollution_index'],
        'Location': f"{item['comparison']['comparison']['location']['latitude']}, {item['comparison']['comparison']['location']['longitude']}",
        'Industry': item['Industry'],
        'Company Size': item['Size'],
        'ESG Score': 100 - (item['esg_results']['pollution_index'] * 100),  # Inverse of pollution index
    }
    for item in data
])

# Streamlit app
st.title("European ESG Data Dashboard")
st.write("Collabse Open ESG reporting for European Companies")

# Filters
st.sidebar.subheader("Filter Data")
selected_size = st.sidebar.multiselect(
    "Select Company Size(s)",
    options=df['Company Size'].unique(),
    default=df['Company Size'].unique()
)
selected_industry = st.sidebar.multiselect(
    "Select Industry(ies)",
    options=df['Industry'].unique(),
    default=df['Industry'].unique()
)

# Filter dataframe
filtered_df = df[
    (df['Company Size'].isin(selected_size)) &
    (df['Industry'].isin(selected_industry))
    ]

st.write("### Filtered Data")
st.dataframe(filtered_df)

# Create graphs
st.write("### ESG Scores")
fig_esg = px.bar(
    filtered_df,
    x='Company Name',
    y='ESG Score',
    color='Industry',
    title="ESG Scores by Company",
    hover_data=['Company Size', 'Location']
)
st.plotly_chart(fig_esg, use_container_width=True)

st.write("### Pollution Index")
fig_pollution = px.bar(
    filtered_df,
    x='Company Name',
    y='Pollution Index',
    color='Industry',
    title="Pollution Index by Company",
    hover_data=['Company Size', 'Location']
)
st.plotly_chart(fig_pollution, use_container_width=True)

# Display detailed information for each company
for company in filtered_df['Company Name']:
    company_data = next(item for item in data if item['Company Name'] == company)
    st.write(f"### Detailed Information for {company}")
    st.write(f"Size: {company_data['Size']}, Industry: {company_data['Industry']}")

    # Normalized Concentrations
    st.write("#### Normalized Concentrations")
    norm_conc = pd.DataFrame(company_data['esg_results']['normalized_concentrations'].items(),
                             columns=['Pollutant', 'Concentration'])
    fig_norm_conc = px.bar(norm_conc, x='Pollutant', y='Concentration', title=f"Normalized Concentrations - {company}")
    st.plotly_chart(fig_norm_conc, use_container_width=True)

    # Pollution Trend
    st.write("#### Pollution Trend")
    pollution_trend = pd.DataFrame(company_data['esg_results']['pollution_trend'].items(),
                                   columns=['Pollutant', 'Trend'])
    fig_trend = px.line(pollution_trend, x='Pollutant', y='Trend', title=f"Pollution Trend - {company}")
    st.plotly_chart(fig_trend, use_container_width=True)

    # Interpretation
    st.write("#### Interpretation")
    st.write(company_data['interpretation']['interpretation'])

    # Pollutant Comparison
    st.write("#### Pollutant Comparison")
    comparison_data = []
    for pollutant, values in company_data['comparison']['comparison']['variables'].items():
        comparison_data.append({
            "Pollutant": pollutant.replace("_conc", "").upper(),
            "Point Value": values["point_value"],
            "Region Mean": values["region_mean"],
            "WHO Limit": values["who_limit"]
        })
    comparison_df = pd.DataFrame(comparison_data)
    fig_comparison = px.bar(comparison_df, x='Pollutant', y=['Point Value', 'Region Mean', 'WHO Limit'],
                            title=f"Pollutant Comparison - {company}", barmode='group', log_y=True)
    fig_comparison.update_layout(yaxis_title="Concentration (log scale)")
    st.plotly_chart(fig_comparison, use_container_width=True)