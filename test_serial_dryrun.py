import time
import json
import logging
from detector import BirdDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSerial")

def run_dryrun():
    logger.info("Starting Serial Deterrent Dryrun Verification...")
    
    # 1. Initialize BirdDetector
    detector = BirdDetector("config.json")
    
    # Check default status
    logger.info(f"Initial Arduino Status: {detector.arduino_status}")
    
    # 2. Test configuration changes
    # Save a temporary config with dummy COM port enabled
    original_config = detector.load_config()
    test_config = original_config.copy()
    test_config["arduino_port"] = "COM99" # Dummy port
    test_config["arduino_enabled"] = True
    
    detector.save_config(test_config)
    logger.info("Saved test config with dummy port COM99 and enabled=True.")
    
    # Let detector load it
    detector.config = detector.load_config()
    detector._init_arduino_serial(detector.config["arduino_port"], detector.config["arduino_enabled"])
    
    logger.info(f"Arduino status with dummy port: {detector.arduino_status}")
    assert "Error" in detector.arduino_status or "Failed" in detector.arduino_status
    logger.info("[OK] Safely failed connection to invalid port COM99 as expected without crashing.")
    
    # 3. Test triggering manual spray when offline
    success, msg = detector.trigger_manual_spray()
    logger.info(f"Manual spray success: {success}, Message: '{msg}'")
    assert success is False
    logger.info("[OK] Safely blocked spray on offline Arduino connection.")
    
    # 4. Restore original config
    detector.save_config(original_config)
    logger.info("Original config restored successfully.")
    
    logger.info("All serial dry-run tests passed successfully!")

if __name__ == "__main__":
    run_dryrun()
