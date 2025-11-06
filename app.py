#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask web application to display station list
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import os

app = Flask(__name__)
DB_PATH = "kok_data.db"

# Enable CORS and remove security restrictions for local development
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def get_stations():
    """Get all stations from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT 
            id,
            "\ufeffแม่น้ำ" as river,
            "สถานี" as station,
            "บริเวณที่เก็บ" as location,
            "ตำบล" as tambon,
            "อำเภอ" as amphoe,
            "จังหวัด" as province
        FROM station_data
        ORDER BY "\ufeffแม่น้ำ", "สถานี"
    """)
    
    stations = []
    for row in cursor.fetchall():
        station_dict = dict(row)
        # Clean up whitespace from all string fields
        for key, value in station_dict.items():
            if isinstance(value, str):
                station_dict[key] = value.strip()
        stations.append(station_dict)
    
    conn.close()
    
    return stations

@app.route('/')
def index():
    """Main page showing station list"""
    try:
        stations = get_stations()
        
        # Get unique values for filters
        unique_rivers = sorted(list(set([s['river'] for s in stations if s['river']])))
        unique_provinces = sorted(list(set([s['province'] for s in stations if s['province']])))
        unique_tambons = sorted(list(set([s['tambon'] for s in stations if s['tambon']])))
        unique_amphoes = sorted(list(set([s['amphoe'] for s in stations if s['amphoe']])))
        
        # Build hierarchical structure for cascading dropdowns
        # Structure: {province: {amphoe: [tambon1, tambon2, ...]}}
        location_hierarchy = {}
        for station in stations:
            prov = station.get('province', '')
            amph = station.get('amphoe', '')
            tamb = station.get('tambon', '')
            
            if prov and amph and tamb:
                if prov not in location_hierarchy:
                    location_hierarchy[prov] = {}
                if amph not in location_hierarchy[prov]:
                    location_hierarchy[prov][amph] = set()
                location_hierarchy[prov][amph].add(tamb)
        
        # Convert sets to sorted lists
        for prov in location_hierarchy:
            for amph in location_hierarchy[prov]:
                location_hierarchy[prov][amph] = sorted(list(location_hierarchy[prov][amph]))
        
        return render_template('index.html', 
                             stations=stations,
                             unique_rivers=unique_rivers,
                             unique_provinces=unique_provinces,
                             unique_tambons=unique_tambons,
                             unique_amphoes=unique_amphoes,
                             location_hierarchy=location_hierarchy)
    except Exception as e:
        return f"Error loading page: {str(e)}", 500

@app.route('/api/stations')
def api_stations():
    """API endpoint for stations data"""
    stations = get_stations()
    return jsonify(stations)

@app.route('/test')
def test():
    """Simple test endpoint"""
    return "Flask app is working!"

def get_station_by_code(station_code):
    """Get station information by station code"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT 
            id,
            "\ufeffแม่น้ำ" as river,
            "สถานี" as station,
            "บริเวณที่เก็บ" as location,
            "ตำบล" as tambon,
            "อำเภอ" as amphoe,
            "จังหวัด" as province
        FROM station_data
        WHERE TRIM("สถานี") = ?
    """, (station_code.strip(),))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        station_dict = dict(row)
        # Clean up whitespace
        for key, value in station_dict.items():
            if isinstance(value, str):
                station_dict[key] = value.strip()
        return station_dict
    return None

def get_water_data(station_code):
    """Get water quality data for a station, organized as pivot table"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT 
            "\ufeffสิ่งที่ตรวจ" as parameter,
            "ที่ตั้ง" as location,
            "ครั้งที่ตรวจ" as check_number,
            "ค่าที่ได้" as value,
            "ค่าที่วัดได้" as numeric_value,
            "หน่วย" as unit
        FROM water_data
        WHERE TRIM("สถานี") = ?
        ORDER BY CAST("ครั้งที่ตรวจ" AS INTEGER), "\ufeffสิ่งที่ตรวจ"
    """, (station_code.strip(),))
    
    # Organize data as pivot table: {parameter: {check_number: value}}
    pivot_data = {}
    numeric_data = {}  # Store numeric values from database
    check_numbers = set()
    unit_info = {}  # Store unit for each parameter
    
    for row in cursor.fetchall():
        row_dict = dict(row)
        # Clean up whitespace
        for key, value in row_dict.items():
            if isinstance(value, str):
                row_dict[key] = value.strip()
        
        param = row_dict['parameter']
        check_num = row_dict['check_number']
        value = row_dict['value']
        numeric_value = row_dict.get('numeric_value', 0) if row_dict.get('numeric_value') is not None else 0  # Get from database column
        unit = row_dict['unit']
        
        # Don't filter here - keep all data for table display
        # Use numeric_value from database for chart
        
        if param not in pivot_data:
            pivot_data[param] = {}
            numeric_data[param] = {}
            unit_info[param] = unit
        
        # Try to extract numeric check number for sorting
        try:
            check_num_int = int(check_num)
            check_numbers.add(check_num_int)
            pivot_data[param][check_num_int] = value
            numeric_data[param][check_num_int] = numeric_value
        except ValueError:
            # If not numeric, use as-is
            check_numbers.add(check_num)
            pivot_data[param][check_num] = value
            numeric_data[param][check_num] = numeric_value
    
    conn.close()
    
    # Sort check numbers
    sorted_checks = sorted([c for c in check_numbers if isinstance(c, int)]) + \
                    sorted([c for c in check_numbers if not isinstance(c, int)])
    
    # Convert to list format for easier template rendering (all data for table)
    parameters = sorted(pivot_data.keys())
    pivot_list = []
    for param in parameters:
        row_data = {'parameter': param, 'check_values': {}, 'unit': unit_info.get(param, '')}
        for check_num in sorted_checks:
            # Convert check_num to string for easier template access
            value = pivot_data[param].get(check_num, None)
            if value:
                row_data['check_values'][str(check_num)] = value
            else:
                row_data['check_values'][str(check_num)] = None
        pivot_list.append(row_data)
    
    # Create filtered dataframe for chart - use numeric_value from database
    pivot_list_filtered = []
    for param in parameters:
        row_data_filtered = {'parameter': param, 'check_values': {}, 'numeric_values': {}, 'unit': unit_info.get(param, '')}
        for check_num in sorted_checks:
            value = pivot_data[param].get(check_num, None)
            numeric_value = numeric_data[param].get(check_num, 0) if param in numeric_data else 0
            
            if value:
                # Keep original value in check_values (for display)
                row_data_filtered['check_values'][str(check_num)] = value
                # Use numeric_value from database
                row_data_filtered['numeric_values'][str(check_num)] = numeric_value
            else:
                row_data_filtered['check_values'][str(check_num)] = None
                row_data_filtered['numeric_values'][str(check_num)] = 0
        # Always add to filtered list
        pivot_list_filtered.append(row_data_filtered)
    
    return {
        'pivot': pivot_data,
        'pivot_list': pivot_list,  # All data for table
        'pivot_list_filtered': pivot_list_filtered,  # Filtered data for chart
        'check_numbers': sorted_checks,
        'units': unit_info,
        'parameters': parameters
    }

def get_soil_data(station_code):
    """Get soil quality data for a station, organized as pivot table"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT 
            "สารที่ตรวจ" as parameter,
            "บริเวณจุดเก็บ" as location,
            "ครั้งที่ตรวจ" as check_number,
            "ค่าที่ได้" as value,
            "ค่าที่วัดได้" as numeric_value
        FROM soil_data
        WHERE TRIM("สถานี") = ?
        ORDER BY "ครั้งที่ตรวจ", "สารที่ตรวจ"
    """, (station_code.strip(),))
    
    # Organize data as pivot table: {parameter: {check_number: value}}
    pivot_data = {}
    numeric_data = {}  # Store numeric values from database
    check_numbers = set()
    
    for row in cursor.fetchall():
        row_dict = dict(row)
        # Clean up whitespace
        for key, value in row_dict.items():
            if isinstance(value, str):
                row_dict[key] = value.strip()
        
        param = row_dict['parameter']
        check_num = row_dict['check_number']
        value = row_dict['value']
        numeric_value = row_dict.get('numeric_value', 0) if row_dict.get('numeric_value') is not None else 0
        
        # Don't filter here - keep all data for table display
        # Use numeric_value from database for chart
        
        if param not in pivot_data:
            pivot_data[param] = {}
            numeric_data[param] = {}
        
        # Extract check number (handle "ครั้งที่ 1" format)
        check_num_clean = check_num.replace('ครั้งที่', '').strip()
        try:
            check_num_int = int(check_num_clean)
            check_numbers.add(check_num_int)
            pivot_data[param][check_num_int] = value
            numeric_data[param][check_num_int] = numeric_value
        except ValueError:
            check_numbers.add(check_num)
            pivot_data[param][check_num] = value
            numeric_data[param][check_num] = numeric_value
    
    conn.close()
    
    # Sort check numbers
    sorted_checks = sorted([c for c in check_numbers if isinstance(c, int)]) + \
                    sorted([c for c in check_numbers if not isinstance(c, int)])
    
    # Convert to list format for easier template rendering (all data for table)
    parameters = sorted(pivot_data.keys())
    pivot_list = []
    for param in parameters:
        row_data = {'parameter': param, 'check_values': {}}
        for check_num in sorted_checks:
            # Convert check_num to string for easier template access
            value = pivot_data[param].get(check_num, None)
            if value:
                row_data['check_values'][str(check_num)] = value
            else:
                row_data['check_values'][str(check_num)] = None
        pivot_list.append(row_data)
    
    # Create filtered dataframe for chart - use numeric_value from database
    pivot_list_filtered = []
    for param in parameters:
        row_data_filtered = {'parameter': param, 'check_values': {}, 'numeric_values': {}}
        for check_num in sorted_checks:
            value = pivot_data[param].get(check_num, None)
            numeric_value = numeric_data[param].get(check_num, 0) if param in numeric_data else 0
            
            if value:
                # Keep original value in check_values (for display)
                row_data_filtered['check_values'][str(check_num)] = value
                # Use numeric_value from database
                row_data_filtered['numeric_values'][str(check_num)] = numeric_value
            else:
                row_data_filtered['check_values'][str(check_num)] = None
                row_data_filtered['numeric_values'][str(check_num)] = 0
        # Always add to filtered list
        pivot_list_filtered.append(row_data_filtered)
    
    return {
        'pivot': pivot_data,
        'pivot_list': pivot_list,  # All data for table
        'pivot_list_filtered': pivot_list_filtered,  # Filtered data for chart
        'check_numbers': sorted_checks,
        'parameters': parameters
    }

@app.route('/station/<station_code>')
def station_detail(station_code):
    """Display detailed information for a specific station"""
    try:
        station = get_station_by_code(station_code)
        if not station:
            return f"ไม่พบสถานี: {station_code}", 404
        
        water_data = get_water_data(station_code)
        soil_data = get_soil_data(station_code)
        
        return render_template('station_detail.html',
                             station=station,
                             water_data=water_data,
                             soil_data=soil_data)
    except Exception as e:
        return f"Error loading station: {str(e)}", 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 กำลังเริ่มเว็บแอปพลิเคชัน...")
    print("=" * 50)
    print(f"📊 ฐานข้อมูล: {DB_PATH}")
    print(f"🌐 เปิดเบราว์เซอร์ที่: http://localhost:8080")
    print(f"🌐 หรือ: http://127.0.0.1:8080")
    print("=" * 50)
    print("กด Ctrl+C เพื่อหยุดการทำงาน")
    print("=" * 50)
    try:
        # Use threaded=True to handle multiple requests
        # Use 0.0.0.0 to allow connections from all interfaces
        # Port 8080 instead of 5000 (5000 is used by AirPlay on macOS)
        app.run(debug=True, host='0.0.0.0', port=8080, threaded=True, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print("\n❌ Error: Port 8080 ถูกใช้งานอยู่แล้ว")
            print("💡 แนะนำ: ปิดโปรแกรมอื่นที่ใช้ port 8080 หรือเปลี่ยน port")
            print("   ตัวอย่าง: app.run(debug=True, host='0.0.0.0', port=8081)")
        else:
            print(f"\n❌ Error: {e}")

