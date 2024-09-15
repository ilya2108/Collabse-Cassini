import streamlit as st
from static import *
import pandas as pd
from geopy.geocoders import Nominatim
import ssl
import certifi
import requests

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
               # Display the latitude and longitude
               elevation = get_elevation(location.latitude, location.longitude)
               #st.write(f"Latitude: {location.latitude}, Longitude: {location.longitude}, Elevation: {elevation}")
   
               # Create a dataframe with the location coordinates
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
        st.map(address_data["map_data"])
    submit_button = st.form_submit_button(label='Submit')

if submit_button:
    st.success(f"""
               Search the ESG data on '{company_name}':
               ({address_data["map_data"].values[0]}),
               {address_data['elevation']}
               
               """)