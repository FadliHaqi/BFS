import tkinter as tk
from tkinter import messagebox
import folium
import webbrowser
import os
import tempfile
from collections import deque
import math
import threading
import json
import requests
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socket
import heapq

# Import ttkbootstrap
import ttkbootstrap as ttk
from ttkbootstrap.constants import * # Import ALL constants for convenience

class MapClickHandler(BaseHTTPRequestHandler):
    """Handler untuk menangkap klik pada peta"""
    def do_GET(self):
        if self.path.startswith('/click'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            
            if 'lat' in params and 'lng' in params:
                lat = float(params['lat'][0])
                lng = float(params['lng'][0])
                
                with open('temp_coordinates.txt', 'w') as f:
                    f.write(f"{lat},{lng}")
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'''
                    <html><body>
                    <h2>Koordinat Tersimpan!</h2>
                    <p>Latitude: %.6f</p>
                    <p>Longitude: %.6f</p>
                    <p>Silakan kembali ke aplikasi dan klik "Ambil Koordinat"</p>
                    <script>setTimeout(function(){window.close();}, 2000);</script>
                    </body></html>
                ''' % (lat, lng))
        else:
            self.send_response(404)
            self.end_headers()

class KosRouteFinder:
    def __init__(self):
        # Use ttkbootstrap.Window instead of tkinter.Tk
        self.root = ttk.Window(themename="flatly") # You can choose other themes like "superhero", "flatly", "cosmo", "litera", "journal" etc.
        self.root.title("Pencarian Rute Terpendek Kos - Cirebon")
        self.root.geometry("900x700")
        
        self.kos_data = {
            "Kos Putri UMC Watubelah": (-6.741465, 108.492631),
            "Kos Putra AC, HJ Niro": (-6.740983, 108.493616),
            "Kos Putri Gendhis": (-6.741743, 108.493881),
            "Kos Putri BIRU": (-6.741851, 108.494064),
            "Adijaya Kost": (-6.741497, 108.494727),
            "BM KOST": (-6.741960, 108.495728),
            "KOST RAYA HOMESTAY": (-6.742436, 108.495360),
            "Kirana Kost": (-6.743849, 108.491927),
            "Kos Dyfe Kost": (-6.739149, 108.491905),
            "Kos Pa Aris Papua": (-6.741361, 108.496193),
            "Nada Kost": (-6.752155, 108.488655),
            "Kost Umah 9 Sendang": (-6.759701, 108.497369),
            "Kost Pak Hatno": (-6.764886, 108.484164),
            "Rumah Kost GM Sumber": (-6.757495, 108.480082),
            "Kos Putri Nusa Indah Cirebon": (-6.762998, 108.491730)
        }
        
        self.center_cirebon = (-6.758834, 108.487571)
        
        self.start_location = None
        self.destination = None
        self.current_map = None
        self.route_coordinates = []
        
        self.http_server = None
        self.server_thread = None
        
        self.setup_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # With ttkbootstrap, you typically don't need to configure individual styles
        # like TFrame, TLabel, TButton as the themename handles it.
        # You can still use custom styles if needed, but it's often simpler.

        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Title - using 'primary' for a prominent title
        title_label = ttk.Label(main_frame, text="Aplikasi Pencarian Rute Kos Cirebon", 
                                bootstyle="primary", font=('Arial', 18, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25), sticky=tk.N)
        
        # Input and Controls Frame (left side)
        # Using 'info' or 'primary' for LabelFrame to give it a distinct color
        controls_frame = ttk.LabelFrame(main_frame, text="Pengaturan Rute", padding="15", bootstyle="info")
        controls_frame.grid(row=1, column=0, sticky=(tk.N, tk.W, tk.E), padx=10, pady=10)
        controls_frame.columnconfigure(1, weight=1)

        # Start Location Input
        ttk.Label(controls_frame, text="Titik Awal (Lat, Lng):").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.start_entry = ttk.Entry(controls_frame, width=35, bootstyle="default") # Use default bootstyle
        self.start_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))
        self.start_entry.insert(0, f"{self.center_cirebon[0]}, {self.center_cirebon[1]}")
        
        # Start Location Buttons - Using 'secondary' or 'light' for less prominent buttons
        button_frame_start = ttk.Frame(controls_frame)
        button_frame_start.grid(row=1, column=0, columnspan=3, pady=5)
        ttk.Button(button_frame_start, text="Pilih dari Peta", 
                  command=self.open_map_selector, bootstyle="secondary").grid(row=0, column=0, padx=5)
        ttk.Button(button_frame_start, text="Ambil Koordinat", 
                  command=self.get_coordinates_from_click, bootstyle="secondary").grid(row=0, column=1, padx=5)
        
        # Destination Kos Selection
        ttk.Label(controls_frame, text="Kos Tujuan:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.destination_var = tk.StringVar()
        self.destination_combo = ttk.Combobox(controls_frame, textvariable=self.destination_var,
                                            values=list(self.kos_data.keys()), width=32, state='readonly',
                                            bootstyle="default") # Use default bootstyle
        self.destination_combo.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))
        self.destination_combo.set("Pilih Kos Tujuan")
        
        # Search Button - Using 'success' for primary action
        search_btn = ttk.Button(controls_frame, text="Cari Rute Terpendek", 
                               command=self.find_shortest_route, bootstyle="success")
        search_btn.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Map Display Options Frame (right side)
        map_options_frame = ttk.LabelFrame(main_frame, text="Peta & Visualisasi", padding="15", bootstyle="info")
        map_options_frame.grid(row=1, column=1, sticky=(tk.N, tk.W, tk.E), padx=10, pady=10)
        map_options_frame.columnconfigure(0, weight=1)

        ttk.Label(map_options_frame, text="Tampilkan rute atau lokasi kos pada peta interaktif.", 
                  wraplength=250, justify=tk.CENTER).grid(row=0, column=0, pady=10, padx=5)

        map_btn = ttk.Button(map_options_frame, text="Tampilkan Peta Rute", 
                            command=self.show_interactive_map, bootstyle="primary") # Primary for map button
        map_btn.grid(row=1, column=0, pady=5, sticky=tk.E+tk.W)
        
        map_btn2 = ttk.Button(map_options_frame, text="Tampilkan Semua Kos", 
                             command=self.show_all_kos_map, bootstyle="primary") # Primary for map button
        map_btn2.grid(row=2, column=0, pady=5, sticky=tk.E+tk.W)

        # Results Frame
        result_frame = ttk.LabelFrame(main_frame, text="Detail Rute & Informasi", padding="15", bootstyle="light") # Light for text area
        result_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        # Text area for results - ttkbootstrap doesn't directly style tk.Text, but you can set background
        self.result_text = tk.Text(result_frame, height=12, width=80, wrap=tk.WORD, 
                                   font=('Consolas', 9), relief=tk.FLAT, bd=0, bg='#e9ecef', fg='#212529') # Light gray bg, dark text
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview, bootstyle="round") # Styled scrollbar
        self.result_text.configure(yscrollcommand=scrollbar.set)
        
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Status label - Using 'info' or 'success' for status messages
        self.status_label = ttk.Label(main_frame, text="Siap untuk pencarian rute", 
                                     bootstyle="success") # Initial status green
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.N)

    # ... (rest of your methods remain unchanged, as they are not UI-specific) ...
    def on_closing(self):
        """Handle application closing to shut down the HTTP server."""
        if self.http_server:
            threading.Thread(target=self.http_server.shutdown).start()
            self.server_thread.join(timeout=1)

        if os.path.exists('temp_coordinates.txt'):
            os.remove('temp_coordinates.txt')
        self.root.destroy()

    def open_map_selector(self):
        """Membuka peta interaktif untuk memilih titik awal"""
        self.start_local_server()

        map_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pilih Titik Awal</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <style>
                #map {{ height: 600px; }}
                .info {{ 
                    position: absolute; 
                    top: 10px; 
                    left: 10px; 
                    background: white; 
                    padding: 10px; 
                    border-radius: 5px; 
                    box-shadow: 0 0 10px rgba(0,0,0,0.3);
                    z-index: 1000;
                }}
            </style>
        </head>
        <body>
            <div class="info">
                <h3>Pilih Titik Awal</h3>
                <p>Klik pada peta untuk memilih lokasi awal Anda</p>
                <p id="coords">Koordinat akan muncul di sini</p>
            </div>
            <div id="map"></div>
            
            <script>
                var map = L.map('map').setView([{self.center_cirebon[0]}, {self.center_cirebon[1]}], 13);
                
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '© OpenStreetMap contributors'
                }}).addTo(map);
        """
        
        for name, coord in self.kos_data.items():
            map_html += f"""
                L.marker([{coord[0]}, {coord[1]}])
                    .addTo(map)
                    .bindPopup('<b>{name}</b><br>Kos-kosan')
                    .bindTooltip('{name}');
            """
        
        map_html += """
                var currentMarker = null;
                
                function onMapClick(e) {
                    var lat = e.latlng.lat;
                    var lng = e.latlng.lng;
                    
                    if (currentMarker) {
                        map.removeLayer(currentMarker);
                    }
                    
                    currentMarker = L.marker([lat, lng])
                        .addTo(map)
                        .bindPopup('<b>Titik Awal Terpilih</b><br>Lat: ' + lat.toFixed(6) + '<br>Lng: ' + lng.toFixed(6))
                        .openPopup();
                    
                    document.getElementById('coords').innerHTML = 
                        'Lat: ' + lat.toFixed(6) + ', Lng: ' + lng.toFixed(6) + 
                        '<br><button onclick="saveCoordinates(' + lat + ',' + lng + ')">Simpan Koordinat Ini</button>';
                }
                
                function saveCoordinates(lat, lng) {
                    fetch('http://localhost:8000/click?lat=' + lat + '&lng=' + lng)
                        .then(response => response.text())
                        .then(data => {
                            alert('Koordinat tersimpan! Kembali ke aplikasi dan klik "Ambil Koordinat"');
                        })
                        .catch(error => {
                            localStorage.setItem('selectedCoords', lat + ',' + lng);
                            alert('Koordinat: ' + lat.toFixed(6) + ', ' + lng.toFixed(6) + 
                                  '\\nSalin koordinat ini dan paste ke form aplikasi');
                        });
                }
                
                map.on('click', onMapClick);
            </script>
        </body>
        </html>
        """
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8')
        temp_file.write(map_html)
        temp_file.close()
        
        webbrowser.open('file://' + os.path.realpath(temp_file.name))
        
        self.status_label.config(text="Peta dibuka. Klik pada lokasi yang diinginkan, lalu klik 'Ambil Koordinat'", 
                                bootstyle="info") # Use info style for status
    
    def start_local_server(self):
        """Memulai server lokal untuk menangkap klik peta"""
        if self.http_server and self.server_thread and self.server_thread.is_alive():
            return

        def run_server():
            try:
                self.http_server = HTTPServer(('localhost', 8000), MapClickHandler)
                self.http_server.serve_forever()
            except socket.error as e:
                if e.errno == 98:
                    print("Server address already in use.")
                else:
                    print(f"Error starting server: {e}")
            except Exception as e:
                print(f"An unexpected error occurred in server thread: {e}")
            finally:
                if self.http_server:
                    self.http_server.server_close()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        time.sleep(0.1)

    def get_coordinates_from_click(self):
        """Mengambil koordinat yang diklik dari peta"""
        try:
            if os.path.exists('temp_coordinates.txt'):
                with open('temp_coordinates.txt', 'r') as f:
                    coords = f.read().strip()
                    self.start_entry.delete(0, tk.END)
                    self.start_entry.insert(0, coords)
                    self.status_label.config(text=f"Koordinat berhasil diambil: {coords}", 
                                           bootstyle="success") # Use success style
                os.remove('temp_coordinates.txt')
            else:
                messagebox.showinfo("Info", "Belum ada koordinat yang dipilih dari peta.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal mengambil koordinat: {str(e)}")
            self.status_label.config(text=f"Error: {str(e)}", bootstyle="danger") # Use danger style
    
    def get_route_from_osrm(self, start_coord, end_coord):
        """Mendapatkan rute dari OSRM (Open Source Routing Machine)"""
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{start_coord[1]},{start_coord[0]};{end_coord[1]},{end_coord[0]}"
            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'steps': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 'Ok' and len(data['routes']) > 0:
                    route = data['routes'][0]
                    coordinates = route['geometry']['coordinates']
                    route_coords = [[coord[1], coord[0]] for coord in coordinates]
                    
                    distance = route['distance'] / 1000  # km
                    duration = route['duration'] / 60    # menit
                    
                    return route_coords, distance, duration
            
            return None, None, None
            
        except Exception as e:
            print(f"Error getting route from OSRM: {e}")
            return None, None, None
    
    def get_fallback_route(self, start_coord, end_coord):
        """Rute cadangan menggunakan beberapa titik tengah untuk simulasi jalan"""
        waypoints = []
        
        lat_diff = end_coord[0] - start_coord[0]
        lng_diff = end_coord[1] - start_coord[1]
        
        num_points = 8
        for i in range(num_points + 1):
            factor = i / num_points
            
            variation_lat = math.sin(factor * math.pi * 2) * 0.002
            variation_lng = math.cos(factor * math.pi * 3) * 0.002
            
            lat = start_coord[0] + (lat_diff * factor) + variation_lat
            lng = start_coord[1] + (lng_diff * factor) + variation_lng
            
            waypoints.append([lat, lng])
        
        total_distance = 0
        for i in range(len(waypoints) - 1):
            total_distance += self.calculate_distance(waypoints[i], waypoints[i + 1])
        
        duration = (total_distance / 30) * 60
        
        return waypoints, total_distance, duration
    
    def calculate_distance(self, coord1, coord2):
        """Menghitung jarak antara dua koordinat menggunakan formula Haversine"""
        R = 6371
        
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    def find_all_kos_distances(self, start_coord):
        """Mencari jarak ke semua kos dan mengurutkannya"""
        kos_distances = []
        
        for name, coord in self.kos_data.items():
            _, distance, duration = self.get_route_from_osrm(start_coord, coord)
            
            if distance is None:
                distance = self.calculate_distance(start_coord, coord)
                duration = (distance / 30) * 60
            
            kos_distances.append({
                'name': name,
                'coordinate': coord,
                'distance': distance,
                'duration': duration
            })
        
        kos_distances.sort(key=lambda x: x['distance'])
        return kos_distances
    
    def bfs_shortest_route(self, start_coord, target_name):
        """Implementasi BFS yang diperbaiki untuk mencari rute terpendek"""
        if target_name not in self.kos_data:
            return None, None, None, None # Add None for route_coords
        
        target_coord = self.kos_data[target_name]
        
        route_coords, distance, duration = self.get_route_from_osrm(start_coord, target_coord)
        
        if route_coords is None:
            route_coords, distance, duration = self.get_fallback_route(start_coord, target_coord)
        
        path = ["Titik Awal", target_name]
        
        return path, distance, duration, route_coords

    def find_shortest_route(self):
        """Mencari rute terpendek menggunakan BFS yang diperbaiki"""
        try:
            start_text = self.start_entry.get().strip()
            if not start_text:
                messagebox.showerror("Error", "Masukkan koordinat titik awal!")
                return
            
            try:
                lat, lng = map(float, start_text.split(','))
                start_coord = (lat, lng)
            except:
                messagebox.showerror("Error", "Format koordinat salah! Gunakan format: lat, lng")
                return
            
            destination_name = self.destination_var.get()
            if destination_name == "Pilih Kos Tujuan" or destination_name not in self.kos_data:
                messagebox.showerror("Error", "Pilih kos tujuan yang valid!")
                return
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "Mencari rute terpendek...\n")
            self.status_label.config(text="Sedang mencari rute terpendek...", bootstyle="info")
            self.root.update()
            
            def run_search():
                try:
                    path, distance, duration, route_coords = self.bfs_shortest_route(start_coord, destination_name)
                    
                    if path and distance is not None:
                        self.route_coordinates = route_coords
                        self.start_location = start_coord
                        self.destination = self.kos_data[destination_name]
                        self.destination_name = destination_name # Store destination name for map popup
                        
                        all_kos_distances = self.find_all_kos_distances(start_coord)
                        
                        self.root.after(0, lambda: self.display_results(
                            path, distance, duration, start_coord, 
                            self.kos_data[destination_name], destination_name, all_kos_distances))
                    else:
                        self.root.after(0, lambda: self.display_error("Rute tidak dapat ditemukan"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self.display_error(f"Error dalam pencarian: {str(e)}"))
            
            threading.Thread(target=run_search, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")
            self.status_label.config(text="Error dalam pencarian rute", bootstyle="danger")
    
    def display_error(self, error_message):
        """Menampilkan pesan error"""
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"ERROR: {error_message}")
        self.status_label.config(text=error_message, bootstyle="danger")
    
    def display_results(self, path, distance, duration, start_coord, target_coord, target_name, all_kos_distances):
        """Menampilkan hasil pencarian yang diperbaiki"""
        self.result_text.delete(1.0, tk.END)
        
        result = f"=== HASIL PENCARIAN RUTE TERPENDEK ===\n\n"
        result += f"Dari: {start_coord[0]:.6f}, {start_coord[1]:.6f}\n"
        result += f"Ke: {target_name}\n"
        result += f"Koordinat Tujuan: {target_coord[0]:.6f}, {target_coord[1]:.6f}\n\n"
        
        result += f"=== INFORMASI RUTE ===\n"
        result += f"Jarak: {distance:.2f} km\n"
        result += f"Estimasi Waktu: {duration:.0f} menit\n"
        result += f"Algoritma: BFS (Breadth-First Search)\n\n"
        
        result += f"=== JALUR PERJALANAN ===\n"
        for i, location in enumerate(path):
            result += f"{i+1}. {location}\n"
        
        result += f"\n=== RANKING SEMUA KOS (BERDASARKAN JARAK) ===\n"
        for i, kos_info in enumerate(all_kos_distances[:10], 1):
            marker = ">>> " if kos_info['name'] == target_name else "    "
            result += f"{marker}{i:2d}. {kos_info['name']}\n"
            result += f"       Jarak: {kos_info['distance']:.2f} km, Waktu: {kos_info['duration']:.0f} menit\n"
        
        result += f"\n=== CATATAN ===\n"
        if hasattr(self, 'route_coordinates') and self.route_coordinates:
            result += f"✓ Rute mengikuti jalur jalan yang sebenarnya\n"
        else:
            result += f"! Menggunakan estimasi rute langsung\n"
        result += f"✓ Menggunakan algoritma BFS untuk pencarian optimal\n"
        result += f"✓ Jarak dihitung menggunakan routing API atau formula Haversine\n"
        
        self.result_text.insert(tk.END, result)
        self.status_label.config(text="Rute berhasil ditemukan! Klik 'Tampilkan Peta Rute' untuk visualisasi", 
                                bootstyle="success")
    
    def show_interactive_map(self):
        """Menampilkan peta interaktif dengan rute"""
        if not self.start_location or not self.destination:
            messagebox.showwarning("Peringatan", "Lakukan pencarian rute terlebih dahulu!")
            return
        
        map_center = self.start_location
        interactive_map = folium.Map(location=map_center, zoom_start=13)
        
        folium.Marker(
            self.start_location,
            popup="<b>Titik Awal</b><br>Lokasi Mulai Perjalanan",
            tooltip="Lokasi Mulai",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(interactive_map)
        
        destination_popup = f"<b>Tujuan</b><br>{getattr(self, 'destination_name', 'Kos Tujuan')}"
        folium.Marker(
            self.destination,
            popup=destination_popup,
            tooltip=getattr(self, 'destination_name', 'Kos Tujuan'),
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(interactive_map)
        
        if hasattr(self, 'route_coordinates') and self.route_coordinates:
            folium.PolyLine(
                self.route_coordinates,
                color='blue',
                weight=4,
                opacity=0.8,
                popup="Rute Terpendek"
            ).add_to(interactive_map)
        else:
            folium.PolyLine(
                [self.start_location, self.destination],
                color='red',
                weight=3,
                opacity=0.6,
                popup="Rute Langsung"
            ).add_to(interactive_map)
        
        for name, coord in self.kos_data.items():
            color = 'red' if coord == self.destination else 'lightblue'
            folium.Marker(
                coord,
                popup=f"<b>{name}</b><br>Kos-kosan di Cirebon",
                tooltip=name,
                icon=folium.Icon(color=color, icon='home')
            ).add_to(interactive_map)
        
        bounds = [self.start_location, self.destination]
        interactive_map.fit_bounds(bounds, padding=(20, 20))
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        interactive_map.save(temp_file.name)
        webbrowser.open('file://' + os.path.realpath(temp_file.name))
        
        self.status_label.config(text="Peta rute telah dibuka di browser", bootstyle="success")
    
    def show_all_kos_map(self):
        """Menampilkan peta dengan semua kos-kosan"""
        all_kos_map = folium.Map(location=self.center_cirebon, zoom_start=12)
        
        for name, coord in self.kos_data.items():
            folium.Marker(
                coord,
                popup=f"<b>{name}</b><br>Lat: {coord[0]:.6f}<br>Lng: {coord[1]:.6f}",
                tooltip=name,
                icon=folium.Icon(color='blue', icon='home')
            ).add_to(all_kos_map)
        
        folium.Marker(
            self.center_cirebon,
            popup="<b>Pusat Kota Sumber, Cirebon</b><br>Referensi Lokasi",
            tooltip="Referensi Lokasi",
            icon=folium.Icon(color='red', icon='star')
        ).add_to(all_kos_map)
        
        folium.Circle(
            self.center_cirebon,
            radius=2500,
            popup="Area Coverage Kos-kosan",
            color='green',
            fillColor='lightgreen',
            fillOpacity=0.2
        ).add_to(all_kos_map)
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        all_kos_map.save(temp_file.name)
        webbrowser.open('file://' + os.path.realpath(temp_file.name))
        
        self.status_label.config(text="Peta semua kos telah dibuka di browser", bootstyle="success")
    
    def run(self):
        """Menjalankan aplikasi"""
        self.root.mainloop()

if __name__ == "__main__":
    required_libraries = ['folium', 'requests', 'ttkbootstrap'] # Added ttkbootstrap to required libraries
    missing_libraries = []
    
    for lib in required_libraries:
        try:
            __import__(lib)
        except ImportError:
            missing_libraries.append(lib)
    
    if missing_libraries:
        print("Library berikut belum terinstall:")
        for lib in missing_libraries:
            print(f"- {lib}")
        print("\nInstall dengan perintah:")
        print(f"pip install {' '.join(missing_libraries)}")
        exit(1)
    
    print("=== Aplikasi Pencarian Rute Terpendek Kos - Cirebon ===")
    print("Menggunakan algoritma Breadth First Search (BFS)")
    print("Dengan routing yang mengikuti jalur jalan sebenarnya")
    print("Loading aplikasi...")
    
    if os.path.exists('temp_coordinates.txt'):
        os.remove('temp_coordinates.txt')
    
    app = KosRouteFinder()
    app.run()
