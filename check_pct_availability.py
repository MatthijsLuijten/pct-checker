from seleniumbase import SB
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time

# Function definitions (must be before they're called)
def get_current_month_year(sb):
    """Extract current month and year from the page."""
    try:
        # Try to find month/year header - common patterns
        month_elements = sb.find_elements("h2, .fc-toolbar-title, [class*='month'], [class*='title']")
        for elem in month_elements:
            text = elem.text.strip()
            if text and (any(m in text for m in ["March", "April", "May"])):
                return text
    except:
        pass
    return None

def navigate_to_next_month(sb):
    """Navigate to the next month using FullCalendar next button."""
    try:
        next_buttons = sb.find_elements(".fc-next-button")
        if next_buttons:
            next_buttons[0].click()
            sb.sleep(3)
            
            # Wait for calendar to update after navigation
            max_wait = 20
            wait_start = time.time()
            while time.time() - wait_start < max_wait:
                try:
                    date_cells = sb.find_elements("thead td[data-date]")
                    if date_cells and len(date_cells) > 0:
                        # Calendar has updated
                        sb.sleep(2)  # Extra wait for JavaScript to finish
                        return True
                except:
                    pass
                time.sleep(1)
            
            print("Warning: Calendar did not update after navigation, but continuing...")
            return True
        return False
    except Exception as e:
        print(f"Error in navigate_to_next_month: {e}")
        return False

def send_email_notification(available_dates):
    """Send email notification when dates with availability < 35 are found."""
    # Only send email if there are available dates
    if not available_dates:
        print("No available dates found - skipping email notification")
        return False
    
    try:
        # Email configuration - get from environment variables (GitHub Secrets)
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        email_from = os.getenv('EMAIL_FROM')
        email_password = os.getenv('EMAIL_PASSWORD')  # From GitHub Secrets
        email_to = os.getenv('EMAIL_TO').split(',')
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = ', '.join(email_to)  # Join multiple recipients with comma
        
        # Create celebratory email
        msg['Subject'] = '🎉 PCT Permits Available! Time to Hit the Trail! 🥾'
        
        body_lines = [
            "🎊 GREAT NEWS! PCT PERMITS ARE AVAILABLE! 🎊\n",
            "=" * 50,
            "\n",
            "🚶‍♂️ Lace up those hiking boots! 🚶‍♀️\n\n",
            "We found dates with available permits:\n\n"
        ]
        
        for month, date, avail in available_dates:
            body_lines.append(f"  ✨ {month} {date}: {avail} permits available!\n")
        
        body_lines.append("\n🏔️ Don't wait - these spots fill up fast! 🏔️\n")
        body_lines.append("\n📝 Grab your permit here:\n")
        body_lines.append("https://portal.permit.pcta.org/manage/\n")
        body_lines.append("\n" + "=" * 50)
        body_lines.append("\nHappy trails! 🥾🌲")
        
        body = ''.join(body_lines)
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_from, email_password)
        server.send_message(msg)
        server.quit()
        
        print(f"🎉 Celebratory email sent to {', '.join(email_to)}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def parse_availability_from_cells(sb, month_name):
    """Parse availability data from table cells.
    
    Structure:
    - fc-day-grid contains fc-row elements (weeks)
    - Each fc-row has fc-content-skeleton with a table
    - Table thead has fc-day-top cells with data-date and fc-day-number (dates)
    - Table tbody has fc-event-container -> fc-day-grid-event -> fc-content -> fc-title (availability)
    - They're aligned by column position
    """
    available_dates = []
    
    try:
        # Wait for elements to be present before finding them - with retry logic
        date_cells_found = False
        max_retries = 3
        for retry in range(max_retries):
            try:
                sb.wait_for_element_present("thead td[data-date]", timeout=20)
                # Verify we actually found elements
                test_cells = sb.find_elements("thead td[data-date]")
                if test_cells and len(test_cells) > 0:
                    date_cells_found = True
                    break
            except:
                if retry < max_retries - 1:
                    print(f"  Retry {retry + 1}/{max_retries} for {month_name} calendar elements...")
                    sb.sleep(3)
                else:
                    print(f"ERROR: Calendar elements not found for {month_name} after {max_retries} retries")
                    # Try to take a screenshot for debugging
                    try:
                        sb.save_screenshot(f"debug_{month_name}_failed.png")
                        print(f"Screenshot saved as debug_{month_name}_failed.png")
                    except:
                        pass
                    return available_dates
        
        if not date_cells_found:
            return available_dates
        
        # Extra sleep to ensure JavaScript is done rendering
        sb.sleep(2)
        
        all_date_cells = sb.find_elements("thead td[data-date]")
        all_title_elements = sb.find_elements(".fc-day-grid-event .fc-content .fc-title")
        
        print(f"Found {len(all_date_cells)} date cells and {len(all_title_elements)} availability elements")
        
        # Match dates with availability by position (they're in the same order)
        # Empty cells at the start don't have date cells, so indices match 1-to-1
        for i in range(min(len(all_date_cells), len(all_title_elements))):
            try:
                # Get the date
                date_cell = all_date_cells[i]
                data_date = date_cell.get_attribute('data-date')
                if not data_date:
                    continue
                
                day_num = int(str(data_date).split('-')[-1])
                
                # Get the availability number from title element
                try:
                    if i < len(all_title_elements):
                        avail_text = all_title_elements[i].text.strip()
                        
                        if avail_text and avail_text.isdigit():
                            avail_num = 35 - int(avail_text)
                            
                            # Only report if availability is less than 35
                            if avail_num > 0:
                                available_dates.append((day_num, avail_num))
                                print(f"  ✓ {month_name} {day_num}: {avail_num} permits available")
                except Exception as e:
                    pass
                    
            except Exception as e:
                continue
        
    except Exception as e:
        print(f"Error parsing cells: {e}")
        print("Note: Calendar may not have loaded properly. Continuing with other months...")
    
    return available_dates

def _run_main_logic(sb):
    """Main execution logic - runs inside the SB context manager."""
    # Main execution
    print("=== PCT Permit Availability Checker ===")
    
    months_to_check = ["March", "April", "May"]
    found_availability = False
    all_available_dates = []
    
    for month_idx, target_month in enumerate(months_to_check):
        print(f"Checking {target_month}...")
        
        # Parse availability
        available_dates = parse_availability_from_cells(sb, target_month)
        
        if available_dates:
            found_availability = True
            all_available_dates.extend([(target_month, date, avail) for date, avail in available_dates])
        
        # Navigate to next month if not the last one
        if month_idx < len(months_to_check) - 1:
            navigate_to_next_month(sb)
    
    # Summary and email notification
    if found_availability:
        print("\n=== RESULT: Found dates with availability < 35 ===")
        print("\nAvailable dates:")
        for month, date, avail in all_available_dates:
            print(f"  {month} {date}: {avail} permits")
        # Send email only when dates are available
        send_email_notification(all_available_dates)
    else:
        print("\n=== RESULT: All checked dates are full (35) ===")
        print("No email sent - no available dates found")
    
    sb.sleep(5)
    # Context manager will automatically close the browser

# Configure for headless mode (for Raspberry Pi without display)
# Set HEADLESS environment variable to "1" to enable headless mode
# For testing locally, you can uncomment the line below:
headless_mode = os.getenv('HEADLESS', '0') == '1'
headless_mode = True  # Uncomment for local testing

url = "https://portal.permit.pcta.org/availability/mexican-border.php"

print(f"Starting browser in {'headless' if headless_mode else 'normal'} mode...")

# Use SB context manager with undetected Chrome
if headless_mode:
    # Run in headless mode for Raspberry Pi with undetected Chrome
    with SB(uc=True, headless=True) as sb:
        # Set window size before opening URL (faster in headless mode)
        sb.set_window_size(1920, 1080)
        sb.open(url)
        
        # Wait for page to load
        sb.sleep(5)
        
        # Wait up to 60 seconds for the captcha to appear (longer timeout for headless)
        captcha_appeared = False
        start_time = time.time()
        timeout = 60
        print("Waiting for captcha to appear...")
        while time.time() - start_time < timeout:
            try:
                # Look for visible element containing the text "Verify you are human"
                if sb.is_text_visible("Verify you are human"):
                    captcha_appeared = True
                    print("Captcha detected!")
                    break
            except Exception:
                pass
            time.sleep(2)
        
        if not captcha_appeared:
            print("Warning: Captcha did not appear within timeout. Attempting to solve anyway...")
        
        # Solve captcha with retry logic for headless mode
        print("Attempting to solve captcha...")
        try:
            sb.solve_captcha()
            print("Captcha solved!")
        except Exception as e:
            print(f"Error solving captcha: {e}")
            print("Note: Captcha solving in headless mode can be unreliable.")
            print("You may need to use a captcha solving service or run in non-headless mode.")
        
        # Wait for page to load after captcha
        sb.sleep(5)
        
        # Wait for the main content to appear
        page_loaded = False
        start_time = time.time()
        timeout = 60
        print("Waiting for page content to load...")
        while time.time() - start_time < timeout:
            try:
                if sb.is_text_visible("Mexican Border Availability", "h1"):
                    print("Page loaded successfully!")
                    page_loaded = True
                    break
            except Exception:
                pass
            time.sleep(1)
        
        if not page_loaded:
            print("WARNING: Page content (h1) not found within timeout. Checking for calendar anyway...")
        
        # Wait for calendar to be fully loaded - CRITICAL for parsing
        print("Waiting for calendar to fully render...")
        calendar_loaded = False
        max_wait = 45  # Increased timeout for GitHub Actions
        wait_start = time.time()
        
        # First, give JavaScript time to render
        sb.sleep(5)
        
        # Then poll for calendar elements
        while time.time() - wait_start < max_wait:
            try:
                date_cells = sb.find_elements("thead td[data-date]")
                if date_cells and len(date_cells) > 0:
                    print(f"Calendar elements detected! Found {len(date_cells)} date cells")
                    calendar_loaded = True
                    break
            except Exception as e:
                pass
            time.sleep(2)
        
        if not calendar_loaded:
            print("ERROR: Calendar did not load within timeout!")
            print("Attempting to take screenshot for debugging...")
            try:
                sb.save_screenshot("calendar_not_loaded.png")
                print("Screenshot saved as calendar_not_loaded.png")
            except:
                pass
            print("Exiting - cannot proceed without calendar data")
        else:
            # Extra wait to ensure calendar is fully interactive
            sb.sleep(3)
            
            # Main execution code continues here
            _run_main_logic(sb)
else:
    # Run with display (for local testing)
    with SB(uc=True) as sb:
        sb.open(url)
        
        # Wait for page to load
        sb.sleep(5)
        
        # Wait up to 60 seconds for the captcha to appear
        captcha_appeared = False
        start_time = time.time()
        timeout = 60
        print("Waiting for captcha to appear...")
        while time.time() - start_time < timeout:
            try:
                if sb.is_text_visible("Verify you are human"):
                    captcha_appeared = True
                    print("Captcha detected!")
                    break
            except Exception:
                pass
            time.sleep(2)
        
        if not captcha_appeared:
            print("Warning: Captcha did not appear within timeout. Attempting to solve anyway...")
        
        # Solve captcha
        print("Attempting to solve captcha...")
        try:
            sb.solve_captcha()
            print("Captcha solved!")
        except Exception as e:
            print(f"Error solving captcha: {e}")
        
        # Wait for page to load after captcha
        sb.sleep(5)
        
        # Wait for the main content to appear
        page_loaded = False
        start_time = time.time()
        timeout = 60
        print("Waiting for page content to load...")
        while time.time() - start_time < timeout:
            try:
                if sb.is_text_visible("Mexican Border Availability", "h1"):
                    print("Page loaded successfully!")
                    page_loaded = True
                    break
            except Exception:
                pass
            time.sleep(1)
        
        if not page_loaded:
            print("WARNING: Page content (h1) not found within timeout. Checking for calendar anyway...")
        
        # Wait for calendar to be fully loaded
        print("Waiting for calendar to fully render...")
        calendar_loaded = False
        max_wait = 45
        wait_start = time.time()
        
        # First, give JavaScript time to render
        sb.sleep(5)
        
        # Then poll for calendar elements
        while time.time() - wait_start < max_wait:
            try:
                date_cells = sb.find_elements("thead td[data-date]")
                if date_cells and len(date_cells) > 0:
                    print(f"Calendar elements detected! Found {len(date_cells)} date cells")
                    calendar_loaded = True
                    break
            except Exception:
                pass
            time.sleep(2)
        
        if not calendar_loaded:
            print("ERROR: Calendar did not load within timeout!")
            print("Exiting - cannot proceed without calendar data")
        else:
            # Extra wait to ensure calendar is fully interactive
            sb.sleep(3)
            
            # Main execution code continues here
            _run_main_logic(sb)
