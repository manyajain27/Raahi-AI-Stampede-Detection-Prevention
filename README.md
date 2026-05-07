# Rahee - Crowd Management & Event Safety

Rahee is an AI-powered crowd management platform aiming to predict, simulate, and prevent stampedes in event venues. This modular system uses live feeds to detect densities, hardware alerts (ESP32) for physical warnings, and simulation engines for predictive analysis.

## Project Structure
The project is built as a set of separate microservices/modules, typically running on their own ports:
- **dashboard/**: The main user interface (Next.js server).
- **Backend/**: General API service.
- **crowd_simulation/**: Simulates crowd pathing and congestion using defined layouts.
- **Floor_planner/**: A tool to create or edit venue layouts.
- **live_detection/**: Uses YOLO to detect live crowds from a camera feed.
- **Visualizer/**: Visualizes simulation results.
- **esp32/**: Hardware code for on-site IoT alerts.

## How to Run
Since it is highly modular, you must install dependencies in the respective folders and run them individually. Typical flow:
1. Open up separate terminals for each module you want to run.
2. cd into the module folder (e.g., cd dashboard).
3. Follow the specific install/run commands inside that module's README.md.
