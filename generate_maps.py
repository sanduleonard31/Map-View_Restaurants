"""
Restaurant Zone Map Generator
Generates interactive HTML maps for each zone with restaurant locations.
Uses folium for fast rendering with OpenStreetMap tiles.
"""

import csv
import os
import urllib.parse
import hashlib
import folium
from folium import plugins


# București sector approximate center coordinates
SECTOR_CENTERS = {
    '1': (44.4720, 26.0850),  # Sector 1 - North
    '2': (44.4380, 26.1350),  # Sector 2 - East
    '3': (44.4100, 26.1450),  # Sector 3 - Southeast
    '4': (44.4050, 26.0900),  # Sector 4 - South
    '5': (44.4200, 26.0500),  # Sector 5 - Southwest
    '6': (44.4450, 26.0200),  # Sector 6 - West
}

# Colors for different restaurant types
TYPE_COLORS = {
    'pizzerie': 'red',
    'bistro': 'blue',
    'restaurant': 'green',
    'restaurant italian': 'orange',
    'italian restaurant': 'orange',
    'italian bistro': 'purple',
    'restaurant românesc': 'darkgreen',
    'restaurant japonez': 'pink',
    'restaurant asiatic': 'pink',
    'restaurant mediteranean': 'cadetblue',
    'restaurant internațional': 'darkblue',
    'restaurant libanez': 'beige',
    'restaurant/bistro': 'lightblue',
    'pizzerie/bistro': 'lightred',
    'restaurant/bar': 'darkpurple',
}


def get_marker_color(rest_type: str) -> str:
    """Get marker color based on restaurant type."""
    rest_type_lower = rest_type.lower()
    
    # Check for exact match first
    if rest_type_lower in TYPE_COLORS:
        return TYPE_COLORS[rest_type_lower]
    
    # Check for partial matches
    if 'pizz' in rest_type_lower:
        return 'red'
    elif 'bistro' in rest_type_lower:
        return 'blue'
    elif 'italian' in rest_type_lower:
        return 'orange'
    elif 'japonez' in rest_type_lower or 'asiatic' in rest_type_lower:
        return 'pink'
    elif 'românesc' in rest_type_lower:
        return 'darkgreen'
    else:
        return 'green'


def get_marker_icon(rest_type: str) -> str:
    """Get Font Awesome icon based on restaurant type."""
    rest_type_lower = rest_type.lower()
    
    if 'pizz' in rest_type_lower:
        return 'pizza-slice'
    elif 'bistro' in rest_type_lower:
        return 'coffee'
    elif 'bar' in rest_type_lower:
        return 'glass-martini'
    elif 'japonez' in rest_type_lower or 'sushi' in rest_type_lower:
        return 'fish'
    else:
        return 'utensils'


def generate_pseudo_coordinates(name: str, address: str, center: tuple, index: int, total: int) -> tuple:
    """
    Generate pseudo-coordinates for a restaurant based on its name and address.
    Distributes points around the sector center in a spiral pattern.
    """
    # Create a hash from name and address for consistent positioning
    hash_input = f"{name}{address}".encode('utf-8')
    hash_value = int(hashlib.md5(hash_input).hexdigest()[:8], 16)
    
    # Calculate position in a spiral pattern around center
    import math
    
    # Spiral parameters
    angle = (hash_value % 360) * (math.pi / 180)
    
    # Distance from center varies based on index (0.005 to 0.025 degrees ≈ 0.5-2.5 km)
    radius = 0.005 + (hash_value % 1000) / 50000
    
    # Add some variation based on index
    angle += (index / total) * 2 * math.pi
    
    lat = center[0] + radius * math.cos(angle)
    lng = center[1] + radius * math.sin(angle) * 1.5  # Adjust for longitude scaling
    
    return (lat, lng)


def create_google_maps_link(address: str, name: str) -> str:
    """Generate a Google Maps search URL."""
    search_query = f"{name}, {address}, București, Romania"
    encoded_query = urllib.parse.quote(search_query)
    return f"https://www.google.com/maps/search/?api=1&query={encoded_query}"


def read_csv_data(filepath: str) -> dict:
    """Read restaurant data from CSV and organize by zone."""
    zones = {}
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) >= 4:
                zone = row[0].strip()
                restaurant = {
                    'name': row[1].strip(),
                    'address': row[2].strip(),
                    'type': row[3].strip()
                }
                if zone not in zones:
                    zones[zone] = []
                zones[zone].append(restaurant)
    return zones


def create_zone_map(zone: str, restaurants: list, output_dir: str):
    """Create an interactive map for a specific zone."""
    
    # Get center coordinates for this zone
    center = SECTOR_CENTERS.get(zone, (44.4268, 26.1025))  # Default to București center
    
    # Create the map
    m = folium.Map(
        location=center,
        zoom_start=14,
        tiles='OpenStreetMap',
        control_scale=True
    )
    
    # Add alternative tile layers
    folium.TileLayer('cartodbpositron', name='Light Map').add_to(m)
    folium.TileLayer('cartodbdark_matter', name='Dark Map').add_to(m)
    
    # Create marker cluster for better performance with many markers
    marker_cluster = plugins.MarkerCluster(name='Restaurants').add_to(m)
    
    # Add markers for each restaurant
    for idx, restaurant in enumerate(restaurants):
        name = restaurant['name']
        address = restaurant['address']
        rest_type = restaurant['type']
        
        # Generate coordinates
        coords = generate_pseudo_coordinates(name, address, center, idx, len(restaurants))
        
        # Create Google Maps link
        maps_link = create_google_maps_link(address, name)
        
        # Create popup HTML
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
            <h4 style="margin: 0 0 8px 0; color: #2F5496;">{name}</h4>
            <p style="margin: 4px 0; color: #666;">
                <strong>📍 Address:</strong><br>{address}
            </p>
            <p style="margin: 4px 0; color: #666;">
                <strong>🍽️ Type:</strong> {rest_type}
            </p>
            <p style="margin: 8px 0 0 0;">
                <a href="{maps_link}" target="_blank" 
                   style="background: #4285F4; color: white; padding: 6px 12px; 
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    🗺️ Open in Google Maps
                </a>
            </p>
        </div>
        """
        
        # Get marker color and icon
        color = get_marker_color(rest_type)
        icon = get_marker_icon(rest_type)
        
        # Create marker
        folium.Marker(
            location=coords,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{name} ({rest_type})",
            icon=folium.Icon(color=color, icon=icon, prefix='fa')
        ).add_to(marker_cluster)
    
    # Add a legend
    legend_html = f"""
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background: white; padding: 15px; border-radius: 8px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-family: Arial, sans-serif;">
        <h4 style="margin: 0 0 10px 0; color: #2F5496;">🍽️ Sector {zone} Restaurants</h4>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: red;">●</span> Pizzerie</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: blue;">●</span> Bistro</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: orange;">●</span> Italian</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: green;">●</span> Restaurant</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: pink;">●</span> Asian/Japanese</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: darkgreen;">●</span> Romanian</p>
        <hr style="margin: 10px 0;">
        <p style="margin: 0; font-size: 11px; color: #666;">Total: {len(restaurants)} restaurants</p>
        <p style="margin: 5px 0 0 0; font-size: 10px; color: #999;">Click markers for details</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add search functionality
    plugins.Search(
        layer=marker_cluster,
        search_label='name',
        placeholder='Search restaurants...',
        collapsed=False
    ).add_to(m)
    
    # Save map
    output_path = os.path.join(output_dir, f"zone_{zone}_map.html")
    m.save(output_path)
    
    return output_path


def create_overview_map(zones: dict, output_dir: str):
    """Create an overview map with all zones."""
    
    # București center
    center = (44.4268, 26.1025)
    
    # Create the map
    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles='OpenStreetMap',
        control_scale=True
    )
    
    # Add alternative tile layers
    folium.TileLayer('cartodbpositron', name='Light Map').add_to(m)
    folium.TileLayer('cartodbdark_matter', name='Dark Map').add_to(m)
    
    # Create feature groups for each zone
    zone_colors = {
        '1': 'green',
        '2': 'blue', 
        '3': 'orange',
        '4': 'red',
        '5': 'purple',
        '6': 'darkblue'
    }
    
    for zone, restaurants in sorted(zones.items()):
        zone_center = SECTOR_CENTERS.get(zone, center)
        zone_color = zone_colors.get(zone, 'gray')
        
        # Create feature group for this zone
        fg = folium.FeatureGroup(name=f"Sector {zone} ({len(restaurants)} restaurants)")
        
        for idx, restaurant in enumerate(restaurants):
            name = restaurant['name']
            address = restaurant['address']
            rest_type = restaurant['type']
            
            coords = generate_pseudo_coordinates(name, address, zone_center, idx, len(restaurants))
            maps_link = create_google_maps_link(address, name)
            
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 180px;">
                <h4 style="margin: 0 0 5px 0; color: #2F5496; font-size: 13px;">{name}</h4>
                <p style="margin: 3px 0; font-size: 11px;">📍 {address}</p>
                <p style="margin: 3px 0; font-size: 11px;">🍽️ {rest_type}</p>
                <p style="margin: 3px 0; font-size: 11px;">📌 Sector {zone}</p>
                <a href="{maps_link}" target="_blank" 
                   style="font-size: 11px; color: #4285F4;">Open in Google Maps</a>
            </div>
            """
            
            folium.CircleMarker(
                location=coords,
                radius=6,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=name,
                color=zone_color,
                fill=True,
                fillColor=zone_color,
                fillOpacity=0.7
            ).add_to(fg)
        
        fg.add_to(m)
    
    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background: white; padding: 15px; border-radius: 8px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-family: Arial, sans-serif;">
        <h4 style="margin: 0 0 10px 0; color: #2F5496;">🗺️ București Restaurants</h4>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: green;">●</span> Sector 1</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: blue;">●</span> Sector 2</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: orange;">●</span> Sector 3</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: red;">●</span> Sector 4</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: purple;">●</span> Sector 5</p>
        <p style="margin: 5px 0; font-size: 12px;"><span style="color: darkblue;">●</span> Sector 6</p>
        <hr style="margin: 10px 0;">
        <p style="margin: 0; font-size: 10px; color: #999;">Use layer control to toggle zones</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add controls
    plugins.Fullscreen().add_to(m)
    folium.LayerControl().add_to(m)
    
    # Save map
    output_path = os.path.join(output_dir, "all_zones_map.html")
    m.save(output_path)
    
    return output_path


def create_index_page(zones: dict, output_dir: str):
    """Create an index HTML page linking to all maps."""
    
    total_restaurants = sum(len(r) for r in zones.values())
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>București Restaurant Maps</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        .subtitle {{
            color: rgba(255,255,255,0.9);
            text-align: center;
            font-size: 1.1em;
            margin-bottom: 40px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 40px;
        }}
        .stat-box {{
            background: white;
            padding: 20px 30px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .map-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .map-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            text-decoration: none;
            transition: transform 0.3s, box-shadow 0.3s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .map-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}
        .map-card h3 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 1.3em;
        }}
        .map-card p {{
            color: #666;
            font-size: 0.95em;
        }}
        .map-card .emoji {{
            font-size: 2em;
            margin-bottom: 10px;
        }}
        .zone-1 {{ border-left: 4px solid #4CAF50; }}
        .zone-2 {{ border-left: 4px solid #2196F3; }}
        .zone-3 {{ border-left: 4px solid #FF9800; }}
        .zone-4 {{ border-left: 4px solid #f44336; }}
        .zone-5 {{ border-left: 4px solid #9C27B0; }}
        .zone-6 {{ border-left: 4px solid #3F51B5; }}
        .zone-all {{ border-left: 4px solid #667eea; }}
        .overview-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .overview-card h3, .overview-card p {{
            color: white;
        }}
        footer {{
            text-align: center;
            color: rgba(255,255,255,0.7);
            margin-top: 40px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🍽️ București Restaurant Maps</h1>
        <p class="subtitle">Interactive maps for each sector of București</p>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{total_restaurants}</div>
                <div class="stat-label">Total Restaurants</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(zones)}</div>
                <div class="stat-label">Sectors</div>
            </div>
        </div>
        
        <div class="map-grid">
            <a href="all_zones_map.html" class="map-card overview-card zone-all">
                <div class="emoji">🗺️</div>
                <h3>All Zones Overview</h3>
                <p>View all {total_restaurants} restaurants across București</p>
            </a>
"""
    
    zone_emojis = {'1': '🟢', '2': '🔵', '3': '🟠', '4': '🔴', '5': '🟣', '6': '🔷'}
    
    for zone in sorted(zones.keys()):
        count = len(zones[zone])
        emoji = zone_emojis.get(zone, '📍')
        html_content += f"""
            <a href="zone_{zone}_map.html" class="map-card zone-{zone}">
                <div class="emoji">{emoji}</div>
                <h3>Sector {zone}</h3>
                <p>{count} restaurants</p>
            </a>
"""
    
    html_content += """
        </div>
        
        <footer>
            <p>Click on any card to open the interactive map</p>
            <p>Maps powered by OpenStreetMap & Folium</p>
        </footer>
    </div>
</body>
</html>
"""
    
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path


def main():
    csv_path = "data.csv"
    output_dir = "maps"
    
    print("🗺️ Restaurant Map Generator")
    print("=" * 40)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Read data
    print("📖 Reading CSV data...")
    zones = read_csv_data(csv_path)
    
    total = sum(len(r) for r in zones.values())
    print(f"   Found {total} restaurants in {len(zones)} zones")
    
    # Create overview map
    print("\n🌍 Creating overview map...")
    overview_path = create_overview_map(zones, output_dir)
    print(f"   ✅ Created: {overview_path}")
    
    # Create individual zone maps
    print("\n📍 Creating zone maps...")
    for zone in sorted(zones.keys()):
        restaurants = zones[zone]
        print(f"   Zone {zone}: {len(restaurants)} restaurants...", end=" ")
        map_path = create_zone_map(zone, restaurants, output_dir)
        print("✅")
    
    # Create index page
    print("\n📄 Creating index page...")
    index_path = create_index_page(zones, output_dir)
    print(f"   ✅ Created: {index_path}")
    
    print("\n" + "=" * 40)
    print("🎉 Done! Maps generated in the 'maps' folder.")
    print(f"   Open {index_path} in a browser to get started.")
    print("\nFeatures:")
    print("   • Click markers to see restaurant details")
    print("   • Click 'Open in Google Maps' for exact location")
    print("   • Use layer control to toggle zones/map styles")
    print("   • Zoom and pan to explore the map")


if __name__ == "__main__":
    main()
