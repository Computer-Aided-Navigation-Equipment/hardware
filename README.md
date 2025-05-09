# Smart Cane Project

This project integrates multiple sensors and peripherals with a Raspberry Pi to collect data, capture images, and provide feedback through a buzzer. The setup includes GPS, LiDAR, a camera, a temperature sensor, and a buzzer.

## Features

- **GPS Module (GY-GPS6MV2, NEO-6M)**: Reads GPS coordinates in real-time.
- **LiDAR (RPLIDAR A1/A2)**: Collects distance and angle data from the surroundings.
- **Camera (Raspberry Pi Camera)**: Captures images and saves them locally.
- **Buzzer**: Provides audible feedback.
- **Temperature Sensor (MLX90614)**: Measures ambient and object temperature.
- **Object Detection (YOLOv5)**: Detects objects in the captured images.

## Requirements

- Raspberry Pi (with GPIO support)
- Python 3
- Installed libraries:
  - `serial`
  - `RPi.GPIO`
  - `cv2` (OpenCV)
  - `rplidar-roboticia`
  - `pynmea2`
  - `torch` (for YOLOv5)
  - `requests`
  - `dotenv`
  - `adafruit-mlx90614`
  - `geocoder`
- Hardware:
  - GPS Module (GY-GPS6MV2, NEO-6M)
  - RPLIDAR A1/A2
  - Raspberry Pi Camera
  - 2-pin Buzzer
  - MLX90614 Temperature Sensor

## Setup

1. **Connect the hardware**:
   - Connect the GPS module to the Raspberry Pi's UART pins.
   - Connect the LiDAR to a USB port.
   - Connect the camera to the Raspberry Pi's camera interface.
   - Connect the buzzer to GPIO pin 17 (or modify the pin in the code).
   - Connect the MLX90614 temperature sensor to the I2C pins of the Raspberry Pi.

2. **Install dependencies**:
   ```bash
   # Install libraries
   pip install pyserial rplidar-roboticia requests boto3 python-dotenv geocoder adafruit-circuitpython-mlx90614

   # Clone the YOLOv5 repository
   git clone https://github.com/ultralytics/yolov5

   # Navigate to the cloned directory
   cd yolov5
  
   # Install required packages
   pip install -r requirements.txt
   ```

3. **Enable camera support**:
   - Run `sudo raspi-config` and enable the camera interface.
  
4. **Create a `.env` file for storing AWS credentials and other environment variables:**:
   ```env
   PORT=6001
   DBURI=<your-mongodb-uri>
   JWT_SECRET=<your-jwt-secret>

   BREVO_API_KEY=<your brevo-api-key>
   FRONTEND_URL=<your frontend-url>
   
   AWS_ACCESS_KEY_ID=<your-aws-access-key-id>
   AWS_SECRET_ACCESS_KEY=<your-aws-secret-access-key>
   AWS_REGION=<your-aws-region>
   S3_BUCKET_NAME=<your-s3-bucket-name>
   ```

## Usage

1. Clone or copy the project to your Raspberry Pi.
2. Run the script:
   ```bash
   python3 main.py
   ```
3. The script will:
   - Continuously read GPS coordinates and print them.
   - Collect LiDAR data and print the points.
   - Capture an image and save it with a timestamped filename.
   - Measure the ambient and object temperature using the MLX90614 sensor.
   - Beep the buzzer for feedback.
   - Log the location, path, and temperature data in MongoDB.

## Notes

- Ensure the GPS module has a clear view of the sky for accurate readings.
- The LiDAR should be placed in an open area for effective scanning.
- Modify the GPIO pin for the buzzer if needed.
- The MLX90614 temperature sensor needs to be connected to the I2C pins. Ensure I2C is enabled on the Raspberry Pi.
- Make sure to configure your credentials properly in the .env file.

## Cleanup

The script includes a cleanup routine to:
- Close the GPS serial connection.
- Stop and disconnect the LiDAR.
- Release the camera.
- Reset GPIO pins.

## Block Diagram

![block_diagram](https://github.com/user-attachments/assets/110aae23-9228-46e6-a3f6-a9af200b2ada)

## Schematic Diagram

![schematic_diagram](https://github.com/user-attachments/assets/87a190c7-600c-4a28-95a1-88e7277d0675)

## Wiring Diagram

![wiring_diagram](https://github.com/user-attachments/assets/6f58eb5d-45bb-4e47-90b2-e1dc65afd0fd)
