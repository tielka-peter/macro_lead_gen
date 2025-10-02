import sys
import os
# add ../src to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import macro_lead_gen as mg
import streamlit as st
import pandas as pd
import math
from dotenv import load_dotenv
import requests


# initialize session state variables and load env variables
if "i" not in st.session_state:
    st.session_state.i = 0
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "accepted_rows" not in st.session_state:
    st.session_state.accepted_rows = []
if "img_data" not in st.session_state:
    st.session_state.img_data = []
number_photos = 4 # can change to user input later

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")


# functions
def fetch_photo(place_id, number_photos=1):
    details_url = (
        f"https://maps.googleapis.com/maps/api/place/details/json"
        f"?place_id={place_id}&fields=photos&key={API_KEY}"
    )
    details = requests.get(details_url).json()
    
    photos = details.get("result", {}).get("photos", [])
    
    img_data = []
    
    for i in range(min(number_photos, len(photos))):
        photo_ref = photos[i]["photo_reference"]

        photo_url = (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=200&photo_reference={photo_ref}&key={API_KEY}"
        )
        
        img_data.append(requests.get(photo_url).content)
    
    return img_data





# make columns
st.set_page_config(layout="wide")
col1, col2, col3 = st.columns([0.2, 0.4, 0.4], gap="large")
col1.title("Inputs")
col2.title("Filtering")
col3.title("Final Outputs")


# column 1 inputs
col1.subheader("Mandatory Inputs")
suburb = col1.text_input("Enter Suburb", value="Brisbane") # default value for testing
num_leads = int(col1.number_input("Number of Leads", min_value=1, max_value=60, value=5)) # default value for testing
return_format = col1.selectbox("Return Format", options=["raw", "capsule"], index=0) # temporary

col1.subheader("Optional Filters")
state = col1.text_input("Enter State (e.g. VIC)").strip().upper()
descriptor = col1.text_input("Enter Descriptor (e.g. 'fancy', 'affluent', 'bakery' ect.)").strip()

# search button
col1.write("")
search = col1.button("Search")
if search:
    st.session_state.i = 0
    
    if suburb and num_leads:
        kwargs = {"suburb": suburb, "max_leads": num_leads}
        if state:
            kwargs["state"] = state
        if descriptor:
            kwargs["descriptor"] = descriptor
        if return_format == "capsule":
            kwargs["return_format"] = "capsule"
        
        st.session_state.df = mg.cafes_for_suburb(**kwargs) 
        
        
        # fetch photos for each cafe

        for row in st.session_state.df.itertuples():
            st.session_state.img_data.append(fetch_photo(row.place_id, number_photos))
            
            
    
    else:
        col1.error("Please enter a suburb and number of leads.")








# column 2 for manual filtering and display
col21, col22, col2spacer = col2.columns([0.2, 0.15, 0.65])
if col22.button("Next"):
    st.session_state.i += 1
if col21.button("Previous"):
    st.session_state.i += -1
st.session_state.i = max(0, min(st.session_state.i, len(st.session_state.df)-1))    

if col21.button("Accept"):
    st.session_state.accepted_rows.append(st.session_state.i)
    st.balloons()
if col22.button("Reject"):
    st.session_state.accepted_rows.remove(st.session_state.i) if st.session_state.i in st.session_state.accepted_rows else None
st.write(f"Accepted rows: {st.session_state.accepted_rows}")


if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and st.session_state.img_data:
    # get current row to displace
    row = st.session_state.df.iloc[st.session_state.i]
    row.name = f"Cafe {st.session_state.i + 1}" 
    
    # display filter info
    rating = row.rating
    num_ratings = row.rating_count
    stars = "⭐" * math.floor(rating) + "☆" * (5 - math.floor(rating))
    rating_w_stars = f"{rating} {stars}"
    filter_info = pd.Series({"Name": row.place_name, "Address": row.formatted_address, "Rating": rating_w_stars, "Number of Ratings": num_ratings})
    col2.table(filter_info)
    
    # go to cafe website button
    col2.link_button("Go to cafe website", row.website)
    
    
    # show cafe photos
    col2image1, col2image2 = col2.columns(2)
    
    # display photos
    for i in range(number_photos):
        
        if i >= number_photos / 2:
            col2image1.image(st.session_state.img_data[st.session_state.i][i], use_container_width=True)
        else:
            col2image2.image(st.session_state.img_data[st.session_state.i][i], use_container_width=True)

    
    
    
else:       
    col2.info("No results loaded yet.")
    
    
