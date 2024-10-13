from flask import Flask, render_template, send_from_directory, abort
import pandas as pd
import os
from twilio.rest import Client
import threading  # For running notification in the background
import time  # For managing time delays

# Initialize the Flask app
app = Flask(__name__)

# Twilio configuration
account_sid = 'AC15d1b7b36ed679215e88c4f6956280c7'  # Replace with your Twilio account SID
auth_token = '857cc5d1f19e64a0dda8acea9169cd90'  # Replace with your Twilio auth token
client = Client(account_sid, auth_token)  # Create Twilio client instance

# Variables to store violation counts
time_violations = 0
lane_violations = 0

# Set of already notified violations to prevent duplicates
notified_violations = set()

# Function to send WhatsApp notification
def send_violation_notification(violation):
    try:
        # Send the WhatsApp notification
        message = client.messages.create(
            from_='whatsapp:+14155238886',  # Your Twilio WhatsApp number (e.g., sandbox number)
            body=f"""
            مخالفة:
            وصف المخالفة: دخول الشاحنات والمعدات الثقيلة وما في حكمها إلى المدن أو الخروج منها في الأوقات غير المسموح بها
            قيمة الغرامة: 1000 ريال
            - رصد آلي
            رقم المخالفة: 987654321
            رقم الهوية: 1234567890  
            التاريخ: 2024-10-07  
            الوقت: 01:23:45  
            المدينة: Riyadh 
            السيارة: Mercedes-Benz  

            يمكنكم الاعتراض خلال مدة أقصاها (30) يوماً من خلال منصة أبشر.
            كما يمكنكم زيارة منصة إيفاء: Efaa.sa للسداد. كما يمكنك الاستفادة من تخفيض نسبة 25% بالسداد المبكر.
            """,
            to='whatsapp:+966564341715'  # Your recipient's WhatsApp number
        )
        print(f"WhatsApp message sent: {message.sid}")
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")

# Read CSV files for violation and plate data
output_df = pd.read_csv('output.csv')
detection_logs_df = pd.read_csv('detection_logs.csv')

# Video file paths
video2_path = 'output_video_truck_plate1_converted.mp4'  # Video 1
video1_path = 'output_video.mp4'  # Video 2

# Get plate number from the first row of the CSV
plate_number = output_df.iloc[0]['Plate Number']

@app.route('/')
def index():
    return render_template('index.html', plate_number=plate_number)

@app.route('/video')
def video():
    return render_template('video.html')

# Route to serve Video 1
@app.route('/video1')
def video1():
    try:
        return send_from_directory(directory=os.path.dirname(video1_path), path=os.path.basename(video1_path), mimetype='video/mp4')
    except FileNotFoundError:
        abort(404, description="Video 1 not found")

# Route to serve Video 2
@app.route('/video2')
def video2():
    try:
        return send_from_directory(directory=os.path.dirname(video2_path), path=os.path.basename(video2_path), mimetype='video/mp4')
    except FileNotFoundError:
        abort(404, description="Video 2 not found")

# Route to display plate details
@app.route('/plates')
def plates():
    plates_info = output_df.to_dict(orient='records')
    return render_template('plates.html', plates=plates_info)

# Route to display dashboard with violation statistics
@app.route('/dashboard')
def dashboard():
    # Calculate total number of trucks
    total_trucks = detection_logs_df['Object_ID'].nunique()

    # Calculate violating and non-violating trucks
    violating_trucks = detection_logs_df[detection_logs_df['Violation_Status'] != 'No Violation']['Object_ID'].nunique()
    non_violating_trucks = total_trucks - violating_trucks

    # Hardcoded violation counts (can be adjusted based on detection logs)
    entry_violations = 3  # Number of violations for restricted time entry
    lane_violations = 0  # Number of lane violations

    # Pass data to the dashboard template
    violations_by_class = {
        'مخالفة وقت المنع': entry_violations,
        'مخالفة المسارات': lane_violations
    }

    return render_template('dashboard.html',
                           violations_by_class=violations_by_class,
                           total_trucks=total_trucks,
                           violating_trucks=violating_trucks,
                           non_violating_trucks=non_violating_trucks)

# Function to process violations based on video time
def process_video_for_violations():
    global time_violations, lane_violations

    # Violation events at second 25 and 28
    violation_events = {
        25: 3,  # 3 violations at second 25
        28: 1   # 1 violation at second 28
    }
    
    start_time = time.time()
    for violation_time, violation_count in violation_events.items():
        # Wait until the video reaches the violation time
        while time.time() - start_time < violation_time:
            time.sleep(0.1)  # Check every 100 milliseconds if we've reached the violation time
        
        # Trigger all the violations for this timestamp
        for _ in range(violation_count):
            time_violations += 1
            
            # Trigger WhatsApp notification
            if time_violations not in notified_violations:
                send_violation_notification({"Object_ID": time_violations})
                notified_violations.add(time_violations)

        print(f"Detected {violation_count} violation(s) at second {violation_time}. Total Time Violations = {time_violations}")

# Flask route to provide real-time violation data to the frontend
@app.route('/get_violations')
def get_violations():
    return {
        'time_violations': time_violations,
        'lane_violations': lane_violations
    }

# Trigger violation detection when the user clicks "كشف المخالفات"
@app.route('/violations')
def violations():
    # Start video processing for violations in a background thread
    threading.Thread(target=process_video_for_violations).start()

    # Render the violations page, which will show the video and live counters
    return render_template('violations.html')

# Run the Flask app
if __name__ == "__main__":
    app.run(port=5000, debug=True)
