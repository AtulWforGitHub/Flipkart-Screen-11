Flipkart Login Cookie Refresh - Setup Instructions
====================================================

This tool lets you refresh your Flipkart login so the price-tracking
system keeps working. Run it whenever you're asked to re-login
(for example, if you get logged out of Flipkart).

ONE-TIME SETUP
--------------
1. Install Python (if not already installed):
   https://www.python.org/downloads/
   During install, make sure to check "Add Python to PATH".

2. Install Google Chrome (if not already installed):
   https://www.google.com/chrome/

3. Open Command Prompt in this folder (client-package) and run:
      pip install -r requirements.txt

EVERY TIME YOU NEED TO REFRESH LOGIN
-------------------------------------
1. Open Command Prompt in this folder.
2. Run:
      python flipkart_login.py
3. A Chrome window will open to Flipkart.
4. Click "Login", enter your phone number, then enter the OTP you receive.
5. Once you see you're logged in (your name shows in the top corner),
   go back to the Command Prompt window and press Enter.
6. The tool will save your login and upload it automatically. You'll see
   a confirmation message like "Cookies uploaded to MongoDB as 'primary'".
7. You can close the Chrome window and Command Prompt. Done!

If you see any error messages, take a screenshot and send it over.
