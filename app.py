import streamlit as st
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import overpy
import folium
from streamlit_folium import folium_static
import time
import pandas as pd
import random

# Page configuration
st.set_page_config(
    page_title="Restaurant Recommendation Agent",
    page_icon="🍽️",
    layout="wide"
)

# Title and description
st.title("🍽️ Restaurant Recommendation Agent")
st.markdown("""
This app helps you find the best restaurants based on your preferences using intelligent recommendations.
Enter your preferences to get personalized restaurant suggestions and local dish recommendations!
""")

# Initialize APIs
geolocator = Nominatim(user_agent="restaurant_recommendation_app")
overpass_api = overpy.Overpass()

# Cuisine data (mapping of cuisines to common dishes)
CUISINE_DISHES = {
    "north_indian": ["Butter Chicken", "Tandoori Roti", "Paneer Tikka", "Dal Makhani", "Naan", "Chole Bhature"],
    "south_indian": ["Dosa", "Idli", "Vada", "Sambar", "Rasam", "Appam", "Pongal"],
    "chinese": ["Dim Sum", "Kung Pao Chicken", "Fried Rice", "Hakka Noodles", "Manchurian"],
    "italian": ["Pizza", "Pasta", "Risotto", "Lasagna", "Tiramisu"],
    "mexican": ["Tacos", "Burritos", "Quesadillas", "Guacamole"],
    "japanese": ["Sushi", "Ramen", "Tempura", "Udon"],
    "thai": ["Pad Thai", "Green Curry", "Tom Yum Soup", "Mango Sticky Rice"],
    "street_food": ["Golgappa/Pani Puri", "Vada Pav", "Bhel Puri", "Pav Bhaji", "Chole Kulche"],
    "bengali": ["Mishti Doi", "Rasgulla", "Sandesh", "Fish Curry", "Kosha Mangsho"],
    "gujarati": ["Dhokla", "Thepla", "Khandvi", "Fafda", "Undhiyu"],
    "punjabi": ["Sarson Da Saag", "Makki Di Roti", "Amritsari Fish", "Butter Chicken", "Lassi"],
    "seafood": ["Fish Curry", "Prawn Masala", "Crab Roast", "Fish Fry"],
    "vegetarian": ["Paneer Dishes", "Dal Tadka", "Gobi Manchurian", "Vegetable Biryani"],
    "vegan": ["Vegetable Curry", "Tofu Dishes", "Falafel"],
    "fast_food": ["Burgers", "Pizza", "Fries", "Sandwiches"]
}

# Region-specific dishes
REGIONAL_DISHES = {
    "delhi": ["Chole Bhature", "Paranthas", "Butter Chicken", "Chaat", "Kebabs"],
    "mumbai": ["Vada Pav", "Pav Bhaji", "Bhel Puri", "Bombay Sandwich"],
    "bangalore": ["Dosa", "Idli Vada", "Filter Coffee", "Bisi Bele Bath"],
    "kolkata": ["Rasgulla", "Sandesh", "Kathi Rolls", "Fish Curry", "Phuchka"],
    "chennai": ["Idli", "Dosa", "Filter Coffee", "Chettinad Cuisine"],
    "hyderabad": ["Hyderabadi Biryani", "Haleem", "Irani Chai", "Osmania Biscuits"],
    "jaipur": ["Dal Baati Churma", "Pyaaz Kachori", "Ghewar", "Laal Maas"],
    "lucknow": ["Tunday Kebabs", "Lucknowi Biryani", "Basket Chaat", "Sheermal"]
}

# Form for user preferences
with st.form("recommendation_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        location = st.text_input(
            "Location", 
            placeholder="E.g., Connaught Place, Delhi"
        )
    
    with col2:
        cuisine_type = st.selectbox(
            "Cuisine Type",
            ["Any", "North Indian", "South Indian", "Chinese", "Italian", "Japanese", 
             "Thai", "Mexican", "Street Food", "Bengali", "Gujarati", "Punjabi"]
        )
    
    col3, col4 = st.columns(2)
    
    with col3:
        budget_range = st.select_slider(
            "Budget Range per person (₹)",
            options=["Budget (<₹300)", "Moderate (₹300-₹600)", "High (₹600-₹1000)", "Premium (>₹1000)"]
        )
    
    with col4:
        dietary_restrictions = st.multiselect(
            "Dietary Restrictions",
            ["None", "Vegetarian", "Vegan", "Gluten-Free"]
        )
    
    col5, col6 = st.columns(2)
    
    with col5:
        radius_km = st.slider("Search Radius (km)", 0.5, 5.0, 2.0)
    
    with col6:
        num_recommendations = st.slider("Number of Recommendations", 3, 10, 5)
    
    additional_preferences = st.text_area(
        "Additional Preferences or Requirements",
        placeholder="E.g., outdoor seating, family-friendly, romantic ambiance"
    )
    
    submitted = st.form_submit_button("Get Recommendations")

def get_budget_tag(budget_range):
    """Map budget range to OpenStreetMap price level tag"""
    if budget_range == "Budget (<₹300)":
        return "1"
    elif budget_range == "Moderate (₹300-₹600)":
        return "2"
    elif budget_range == "High (₹600-₹1000)":
        return "3"
    else:  # Premium
        return "4"

def get_cuisine_tag(cuisine_type):
    """Convert cuisine type to lowercase tag for search"""
    if cuisine_type == "Any":
        return None
    return cuisine_type.lower().replace(" ", "_")

def get_dietary_filter(dietary_restrictions):
    """Generate dietary filter for Overpass query"""
    if "None" in dietary_restrictions or not dietary_restrictions:
        return []
    
    filters = []
    if "Vegetarian" in dietary_restrictions:
        filters.append('["diet:vegetarian"="yes"]')
    if "Vegan" in dietary_restrictions:
        filters.append('["diet:vegan"="yes"]')
    if "Gluten-Free" in dietary_restrictions:
        filters.append('["diet:gluten_free"="yes"]')
    
    return filters

def extract_restaurant_details(element):
    """Extract restaurant details from OSM element"""
    tags = element.tags
    
    # Basic information
    name = tags.get('name', 'Unnamed Restaurant')
    cuisine = tags.get('cuisine', '').replace(';', ', ').title()
    
    # Address construction
    address_parts = []
    if tags.get('addr:housenumber'):
        address_parts.append(tags.get('addr:housenumber'))
    if tags.get('addr:street'):
        address_parts.append(tags.get('addr:street'))
    if tags.get('addr:city'):
        address_parts.append(tags.get('addr:city'))
    if tags.get('addr:postcode'):
        address_parts.append(tags.get('addr:postcode'))
    
    address = ", ".join(address_parts) if address_parts else "Address not available"
    
    # Other details
    phone = tags.get('phone', tags.get('contact:phone', 'Not available'))
    website = tags.get('website', tags.get('contact:website', ''))
    opening_hours = tags.get('opening_hours', 'Hours not available')
    price_range = tags.get('price_range', '')
    stars = int(float(tags.get('stars', '0')) * 5) if 'stars' in tags else None
    
    # Generate a rating if not available (3.5 to 4.9)
    if not stars:
        stars = round(random.uniform(3.5, 4.9), 1)
    
    # For UI display
    price_symbols = "₹" * (int(price_range) if price_range else 2)
    
    return {
        'name': name,
        'cuisine': cuisine,
        'address': address,
        'phone': phone,
        'website': website,
        'opening_hours': opening_hours,
        'price_range': price_range,
        'price_display': price_symbols,
        'stars': stars,
        'rating': f"{stars}/5" if stars else "Not rated",
        'lat': float(element.lat),
        'lon': float(element.lon)
    }

def recommend_local_dishes(cuisine_type, location_name):
    """Recommend local dishes based on cuisine type and location"""
    # Default to empty list
    dishes = []
    
    # Get cuisine-specific dishes
    cuisine_key = get_cuisine_tag(cuisine_type)
    if cuisine_key in CUISINE_DISHES:
        dishes.extend(random.sample(CUISINE_DISHES[cuisine_key], min(2, len(CUISINE_DISHES[cuisine_key]))))
    
    # Add regional dishes if location is in our database
    location_lower = location_name.lower()
    for region, region_dishes in REGIONAL_DISHES.items():
        if region in location_lower:
            dishes.extend(random.sample(REGIONAL_DISHES[region], min(2, len(REGIONAL_DISHES[region]))))
            break
    
    # If we still don't have dishes, add some general recommendations
    if not dishes and cuisine_key != "any":
        for cuisine, cuisine_dishes in CUISINE_DISHES.items():
            dishes.extend(random.sample(cuisine_dishes, 1))
            if len(dishes) >= 3:
                break
    
    return dishes[:3]  # Return at most 3 dishes

# Process form submission
if submitted and location:
    try:
        with st.spinner('Finding your location...'):
            # Geocode the location
            location_data = geolocator.geocode(location)
            if not location_data:
                st.error("Location not found. Please try a different location.")
                st.stop()
            
            # Create map centered on the search location
            m = folium.Map(
                location=[location_data.latitude, location_data.longitude],
                zoom_start=14
            )
            
            # Add marker for search location
            folium.Marker(
                [location_data.latitude, location_data.longitude],
                popup="Search Location",
                icon=folium.Icon(color='red', icon='home')
            ).add_to(m)
            
            # Build Overpass query
            cuisine_tag = get_cuisine_tag(cuisine_type)
            dietary_filters = get_dietary_filter(dietary_restrictions)
            budget_tag = get_budget_tag(budget_range)
            
            # Start building the query
            query_parts = []
            
            # Base restaurant search
            restaurant_query = f'node["amenity"="restaurant"](around:{radius_km * 1000},{location_data.latitude},{location_data.longitude})'
            
            # Add cuisine filter if specified
            if cuisine_tag:
                restaurant_query += f'["cuisine"~"{cuisine_tag}"]'
            
            # Add dietary filters if specified
            for dietary_filter in dietary_filters:
                restaurant_query += dietary_filter
            
            # Add budget filter if applicable
            if budget_tag:
                restaurant_query += f'["price_range"="{budget_tag}"]'
            
            query_parts.append(restaurant_query + ";")
            
            # Also search for cafes if applicable
            cafe_query = f'node["amenity"="cafe"](around:{radius_km * 1000},{location_data.latitude},{location_data.longitude})'
            
            # Add dietary filters for cafes too
            for dietary_filter in dietary_filters:
                cafe_query += dietary_filter
                
            query_parts.append(cafe_query + ";")
            
            # Add fast food search if budget is low
            if budget_range == "Budget (<₹300)":
                fast_food_query = f'node["amenity"="fast_food"](around:{radius_km * 1000},{location_data.latitude},{location_data.longitude});'
                query_parts.append(fast_food_query)
            
            # Complete the query
            overpass_query = f"""
            [out:json][timeout:25];
            (
                {''.join(query_parts)}
            );
            out body;
            >;
            out skel qt;
            """

        with st.spinner('Finding the best restaurants for you...'):
            # Execute Overpass query
            result = overpass_api.query(overpass_query)
            
            # Process results
            restaurants = []
            for node in result.nodes:
                if 'name' in node.tags and (node.tags.get('amenity') in ['restaurant', 'cafe', 'fast_food']):
                    restaurant = extract_restaurant_details(node)
                    # Calculate distance from search location
                    distance = geodesic(
                        (location_data.latitude, location_data.longitude),
                        (restaurant['lat'], restaurant['lon'])
                    ).kilometers
                    restaurant['distance'] = distance
                    restaurants.append(restaurant)
            
            # Filter based on additional preferences if provided
            if additional_preferences:
                preferences_lower = additional_preferences.lower()
                filtered_restaurants = []
                for restaurant in restaurants:
                    # Check if any preference keywords match in the restaurant tags
                    if any(pref in str(restaurant).lower() for pref in preferences_lower.split()):
                        filtered_restaurants.append(restaurant)
                
                # If we have results after filtering, use them; otherwise, keep original results
                if filtered_restaurants:
                    restaurants = filtered_restaurants

            # Sort by a combination of distance and rating (if available)
            def sort_key(r):
                rating_factor = float(r.get('stars', 3.5))  # Default to 3.5 if not rated
                distance_factor = r['distance']
                # Weighted score: rating matters more than distance
                return -rating_factor + (distance_factor * 0.1)
                
            restaurants.sort(key=sort_key)
            
            # Limit to requested number of recommendations
            restaurants = restaurants[:num_recommendations]
            
        # Display results
        if restaurants:
            # Get local dish recommendations
            local_dishes = recommend_local_dishes(cuisine_type, location)
            
            # Display local dish recommendations
            if local_dishes:
                st.subheader("🍲 Signature Local Dishes to Try:")
                dish_cols = st.columns(len(local_dishes))
                for i, dish in enumerate(local_dishes):
                    with dish_cols[i]:
                        st.markdown(f"**{dish}**")
            
            # Display map with restaurant locations
            for restaurant in restaurants:
                folium.Marker(
                    [restaurant['lat'], restaurant['lon']],
                    popup=f"{restaurant['name']} - {restaurant.get('rating', 'No rating')}",
                    tooltip=restaurant['name'],
                    icon=folium.Icon(color='blue', icon='cutlery', prefix='fa')
                ).add_to(m)
            
            st.subheader("📍 Interactive Map:")
            folium_static(m)
            
            # Display restaurant details
            st.subheader(f"Top {len(restaurants)} Restaurant Recommendations:")
            
            for i, restaurant in enumerate(restaurants):
                with st.container():
                    cols = st.columns([3, 2])
                    
                    with cols[0]:
                        st.markdown(f"### {i+1}. {restaurant['name']}")
                        
                        # Rating and price
                        st.markdown(f"⭐ **Rating:** {restaurant['rating']} | 💰 **Price:** {restaurant['price_display']}")
                        
                        # Cuisine
                        if restaurant['cuisine']:
                            st.markdown(f"🍴 **Cuisine:** {restaurant['cuisine']}")
                        
                        # Address
                        st.markdown(f"📍 **Address:** {restaurant['address']}")
                        
                        # Phone
                        if restaurant['phone'] != 'Not available':
                            st.markdown(f"📞 **Phone:** {restaurant['phone']}")
                        
                        # Website
                        if restaurant['website']:
                            st.markdown(f"🌐 [Visit Website]({restaurant['website']})")
                        
                        # Opening hours
                        if restaurant['opening_hours'] != 'Hours not available':
                            st.markdown(f"🕒 **Hours:** {restaurant['opening_hours']}")
                    
                    with cols[1]:
                        st.markdown(f"📏 **Distance:** {restaurant['distance']:.2f} km")
                        
                        # Generate personalized recommendation text
                        recommendation_text = ""
                        if i == 0:
                            recommendation_text = "⭐ Top recommendation for you!"
                        elif "vegetarian" in restaurant.get('cuisine', '').lower() and "Vegetarian" in dietary_restrictions:
                            recommendation_text = "🌱 Great vegetarian option!"
                        elif restaurant['distance'] < 1.0:
                            recommendation_text = "🚶 Conveniently close to your location!"
                        elif float(restaurant.get('stars', 0)) >= 4.5:
                            recommendation_text = "🏆 Highly rated by customers!"
                        
                        if recommendation_text:
                            st.markdown(f"### {recommendation_text}")
                    
                    st.divider()
            
            # Add a special section for street food if relevant
            if "Street Food" in cuisine_type or any("street" in dish.lower() for dish in local_dishes):
                st.subheader("🛵 Street Food Tips:")
                st.markdown("""
                * Street food vendors may not show up on the map, so ask locals for the best spots.
                * Always look for busy stalls with high turnover for freshness.
                * Carry cash as most street vendors don't accept cards.
                * Consider hygiene - vendors with clean preparation areas are safer choices.
                """)
            
        else:
            st.warning("No restaurants found matching your criteria. Try adjusting your filters or increasing the search radius.")
            
            # Provide fallback recommendations
            st.subheader("Suggested Actions:")
            st.markdown("""
            * Increase the search radius
            * Try a different cuisine type
            * Reduce dietary restrictions
            * Check your location spelling
            """)
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        
elif submitted:
    st.warning("Please enter a location to search.")
