# Create a directory named GsocWorkplace and navigate into it
mkdir GsocWorkplace  
cd GsocWorkplace   

# Clone the SciCommons-backend repository from GitHub
git clone https://github.com/m2b3/SciCommons-backend
cd SciCommons-backend   

# Open the project in Visual Studio Code
code .                                              

# Set up a Python virtual environment named venv
python -m venv venv  
source venv/bin/activate

# Install Python dependencies listed in requirements.txt
pip install -r requirements.txt

# Set up PostgreSQL database:
# Make sure to create a Database in your PostgreSQL instance

# Create an AWS account:
# Set the following environment variables with appropriate values:

# Create a .env file in the root directory and add the following information:
#Note: Ensure there are no spaces between the variable and value assignment

DATABASE_URL=postgres://username:password@hostname:port_no/database_name 
# Replace placeholders with your PostgreSQL database credentials
# Information for this can be found in your PostgreSQL account

EMAIL_HOST_PASSWORD=//password
# Replace //password with your email host password

AWS_ACCESS_KEY_ID=//Create Secret access key 
# Replace //Create Secret access key with your AWS access key ID
# Information for this can be found in your AWS account

AWS_SECRET_ACCESS_KEY=//Create Secret access key 
# Replace //Create Secret access key with your AWS secret access key
# Information for this can be found in your AWS account

AWS_STORAGE_BUCKET_NAME=//Create S3 bucket 
# Replace //Create S3 bucket with the name of your AWS S3 bucket
# Information for this can be found in your AWS account

SIGNATURE_NAME=Riya 
# Replace Riya with your desired signature in computer form
# Note: Ensure there are no spaces between the variable and value assignment


# Access the PostgreSQL database
psql -d Gsoc_Work -U postgres    

# Install any additional dependencies as required

# Apply database migrations
python manage.py migrate  

# Create a superuser for Django admin access
python manage.py createsuperuser

Provide superuser details:
Username: gsoc-work
Email address: xyz@gmail.com
Password: abc

# Start the Django development server
python manage.py runserver
