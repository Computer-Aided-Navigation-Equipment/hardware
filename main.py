import time
import serial
import pynmea2
from rplidar import RPLidar, RPLidarException
from picamera2 import Picamera2
import board
import busio
from adafruit_mlx90614 import MLX90614
import geocoder
import cv2
import numpy as np
import torch
import os
import jwt
import requests
from boto3 import client
from dotenv import load_dotenv
from datetime import datetime
from gpiozero import Buzzer

# Load environment variables from .env file
load_dotenv()

# === Hardware setup with gpiozero ===
buzzer = Buzzer(17)  # Initialize buzzer on GPIO pin 17

def buzz(times, on=0.1, off=0.1):
    """Activate buzzer with specified pattern"""
    for _ in range(times):
        buzzer.on()
        time.sleep(on)
        buzzer.off()
        time.sleep(off)

# === Load YOLOv5 Model ===
model = torch.hub.load("ultralytics/yolov5", "yolov5s", trust_repo=True)

# === Initialize Temperature Sensor ===
i2c = busio.I2C(board.SCL, board.SDA)
try:
    sensor = MLX90614(i2c)
    print("MLX90614 initialized.")
except ValueError as e:
    print(f"MLX90614 Error: {e}")
    sensor = None

# === Initialize Camera ===
picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())
picam2.start()

# === Setup Serial for GPS ===
gps_serial = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=1)

# === AWS S3 Client Setup ===
try:
    s3 = client('s3', 
                region_name=os.getenv('AWS_REGION'), 
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
except Exception as e:
    print(f"Error initializing S3 client: {e}")
    s3 = None

# === Helper Functions ===
def initialize_lidar():
    """Initialize or reinitialize LIDAR connection"""
    try:
        lidar = RPLidar('/dev/ttyUSB0')
        status, error_code = lidar.get_health()
        print(f"LIDAR Health status: {status}, Error code: {error_code}")
        return lidar
    except Exception as e:
        print(f"Error initializing LIDAR: {e}")
        return None

def is_outdoor():
    try:
        newdata = gps_serial.readline()
        try:
            if b'$GPRMC' in newdata:
                newmsg = pynmea2.parse(newdata.decode('utf-8', errors='ignore'))
                if newmsg.status == 'A' and newmsg.latitude != 0.0 and newmsg.longitude != 0.0:
                    return True
        except UnicodeDecodeError:
            return False
    except Exception as e:
        print(f"GPS check error: {e}")
    return False

def get_gps_location():
    try:
        newdata = gps_serial.readline()
        try:
            if b'$GPRMC' in newdata:
                newmsg = pynmea2.parse(newdata.decode('utf-8', errors='ignore'))
                lat = newmsg.latitude
                lng = newmsg.longitude
                return lat, lng
        except UnicodeDecodeError:
            return None, None
    except Exception as e:
        print(f"GPS error: {e}")
    return None, None

def get_geocoder_location():
    try:
        g = geocoder.ip('me')
        if g.ok and g.latlng and len(g.latlng) >= 2:
            return g.latlng[0], g.latlng[1]
        else:
            print("Geocoder failed to get valid location")
    except Exception as e:
        print(f"Geocoder error: {e}")
    return None, None

def draw_lidar_on_image(image, scan):
    height, width, _ = image.shape
    center_x, center_y = width // 2, height // 2
    scale = 3  # tweak this to zoom in/out on points

    for (_, angle, distance) in scan:
        radians = np.radians(angle - 90)
        x = int(center_x + scale * distance * np.cos(radians))
        y = int(center_y + scale * distance * np.sin(radians))
        if 0 <= x < width and 0 <= y < height:
            cv2.circle(image, (x, y), 10, (0, 0, 255), -1)

    return image

def upload_image_to_s3(image_path, bucket_name):
    if not s3:
        print("S3 client not initialized")
        return None
    try:
        if not os.path.exists(image_path):
            print(f"Image file not found: {image_path}")
            return None
            
        file_name = os.path.basename(image_path)
        with open(image_path, 'rb') as file:
            s3.upload_fileobj(file, bucket_name, file_name)
        url = f"https://{bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{file_name}"
        return url
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return None

def authenticate_user(email, password):
    """Authenticate user and return user data and JWT token"""
    try:
        response = requests.post(
            'http://localhost:6001/api/user/login',
            json={'email': email, 'password': password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print("Authentication successful")
            return data.get('user'), data.get('accessToken')
        else:
            print(f"Authentication failed: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None, None

def save_location_to_db(user_id, jwt_token, lat, lng):
    if lat is None or lng is None:
        print("No location data to save")
        return
        
    location_str = f"{lat},{lng}"
    location_data = {
        "location": location_str,
        "title": f"Auto-location {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    }
    try:
        response = requests.post(
            'http://localhost:6001/api/location/create',
            json=location_data,
            headers={'Authorization': f'Bearer {jwt_token}'},
            timeout=10
        )
        if response.status_code in [200, 201]:
            print(f"Location saved successfully: {response.json().get('message')}")
        else:
            print(f"Error saving location: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error saving location to MongoDB: {e}")

def save_image_url_to_db(user_id, jwt_token, image_url):
    if not image_url:
        print("No image URL to save")
        return
        
    attachment_data = {
        "url": image_url,
        "key": image_url.split("/")[-1],
        "mimeType": "image/jpeg"
    }
    try:
        response = requests.post(
            'http://localhost:6001/api/attachment/create',
            json=attachment_data,
            headers={'Authorization': f'Bearer {jwt_token}'},
            timeout=10
        )
        if response.status_code in [200, 201]:
            print(f"Image URL saved successfully: {response.json().get('message')}")
        else:
            print(f"Error saving image URL: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error saving image URL to MongoDB: {e}")

def save_path_log_to_db(user_id, jwt_token, location, description, miles, obstacles, steps):
    path_log_data = {
        "location": location,
        "description": description,
        "miles": miles,
        "obstacles": obstacles,
        "steps": steps
    }
    try:
        response = requests.post(
            'http://localhost:6001/api/log/create',
            json=path_log_data,
            headers={'Authorization': f'Bearer {jwt_token}'},
            timeout=10
        )
        if response.status_code in [200, 201]:
            print(f"Path Log saved successfully: {response.json().get('message')}")
        else:
            print(f"Error saving path log: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error saving path log to MongoDB: {e}")

# === Main Execution ===
def main_loop():
    # Initialize LIDAR
    lidar = initialize_lidar()
    if lidar is None:
        print("Failed to initialize LIDAR, continuing without LIDAR functionality")
    
    # Only ask for credentials once
    email = input("Enter your email: ")
    password = input("Enter your password: ")
    user_data, jwt_token = authenticate_user(email, password)
    if not user_data or not jwt_token:
        print("User authentication failed. Exiting...")
        return
    
    user_id = user_data.get('_id')
    print(f"Authenticated as user ID: {user_id}")

    while True:
        try:
            print("\n=== Starting new iteration ===")
            
            # === 1. Temperature Sensor ===
            ambient_temp = object_temp = None
            if sensor:
                try:
                    ambient_temp = sensor.ambient_temperature
                    object_temp = sensor.object_temperature
                    print(f"[Temperature] Ambient: {ambient_temp:.2f}°C, Object: {object_temp:.2f}°C")
                except Exception as e:
                    print(f"MLX90614 read error: {e}")

            # === 2. LIDAR Scan ===
            scan = []
            point_count = 0
            if lidar:
                print("Performing LIDAR scan...")
                try:
                    scan = next(lidar.iter_scans(max_buf_meas=6000))
                    point_count = len(scan)
                    print(f"LIDAR scan complete. Points scanned: {point_count}")
                    
                    # Check for nearby objects
                    distances = [m[2] for m in scan]
                    min_dist = min(distances) if distances else float('inf')
                    if min_dist < 300:  # 300 mm threshold
                        print(f"Object detected at {min_dist} mm - activating buzzer!")
                        buzz(3)
                except RPLidarException as e:
                    print(f"LIDAR error: {e}")
                    # Attempt to reconnect
                    try:
                        lidar.stop()
                        lidar.disconnect()
                        time.sleep(1)
                        lidar = initialize_lidar()
                        if lidar is None:
                            print("Failed to reconnect to LIDAR")
                        continue
                    except Exception as e:
                        print(f"Failed to reconnect to LIDAR: {e}")
                        lidar = None
                        continue
                except Exception as e:
                    print(f"Unexpected LIDAR error: {e}")
                    lidar = None
                    continue

            # === 3. Location Detection ===
            lat = lng = None
            location_source = "Unknown"

            if is_outdoor():
                lat, lng = get_gps_location()
                location_source = "GPS (Outdoor)"
            else:
                lat, lng = get_geocoder_location()
                location_source = "Geocoder (Indoor via IP)"

            print(f"Location source: {location_source}")
            if lat is not None and lng is not None:
                print(f"Coordinates: Latitude {lat:.6f}, Longitude {lng:.6f}")
                location_str = f"{lat},{lng}"
            else:
                location_str = None

            # === 4. Capture Camera Image ===
            frame = picam2.capture_array()
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            if lidar and scan:
                fused_image = draw_lidar_on_image(frame, scan)
            else:
                fused_image = frame

            # Add Temperature and GPS Data on the Image
            if ambient_temp is not None and object_temp is not None:
                temp_text = f"Ambient Temp: {ambient_temp:.2f}°C, Object Temp: {object_temp:.2f}°C"
            else:
                temp_text = "Temperature: Unavailable"

            if lat is not None and lng is not None:
                location_text = f"Lat: {lat:.6f}, Lng: {lng:.6f} ({location_source})"
            else:
                location_text = "Location: Unavailable"

            cv2.putText(fused_image, temp_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(fused_image, location_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

            # === 5. YOLOv5 DETECTION ===
            results = model(fused_image)
            results.show()
            
            detections = results.pandas().xyxy[0]
            if not detections.empty:
                print("Objects detected:", detections['name'].tolist())
                buzz(2)

            # === 6. Upload Image to S3 and Save URL ===
            bucket_name = os.getenv('S3_BUCKET_NAME')
            if bucket_name:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                image_path = f"/tmp/image_{timestamp}.jpg"
                try:
                    cv2.imwrite(image_path, cv2.cvtColor(fused_image, cv2.COLOR_RGB2BGR))
                    
                    image_url = upload_image_to_s3(image_path, bucket_name)
                    if image_url:
                        print(f"Image uploaded to S3: {image_url}")
                        save_image_url_to_db(user_id, jwt_token, image_url)
                    else:
                        print("Failed to upload image to S3")
                except Exception as e:
                    print(f"Error saving/uploading image: {e}")
            else:
                print("S3_BUCKET_NAME environment variable not set - skipping S3 upload")

            # === 7. Save Location Data ===
            save_location_to_db(user_id, jwt_token, lat, lng)

            # === 8. Path Log Update ===
            save_path_log_to_db(
                user_id, 
                jwt_token,
                location_str,
                "Automatic path log entry",
                0.0,
                str(detections['name'].tolist()),
                point_count
            )
            
            # Wait before next iteration
            print("Waiting for next cycle...")
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nProgram terminated by user.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            buzz(5, on=0.2, off=0.2)
            time.sleep(5)  # Wait before retrying after error

# === Run the program ===
try:
    main_loop()
finally:
    # Cleanup resources
    try:
        if 'lidar' in locals():
            lidar.stop()
            lidar.disconnect()
    except:
        pass
    picam2.stop()
    buzzer.off()
    print("Shutdown complete.")