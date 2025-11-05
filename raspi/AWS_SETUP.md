# AWS IAM User Setup for S3 Logging

## Step 1: Create IAM User

1. Go to AWS Console → IAM → Users
2. Click "Create user"
3. User name: `raspberrypi-led-logger` (or your preferred name)
4. Select "Provide user access to AWS Management Console" - **OPTIONAL** (uncheck if you only need programmatic access)
5. Click "Next"

## Step 2: Set Permissions

1. Select "Attach policies directly"
2. Click "Create policy" (opens new tab)
3. In the policy editor, select JSON and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        }
    ]
}
```

4. Replace `YOUR-BUCKET-NAME` with your actual S3 bucket name
5. Click "Next"
6. Policy name: `RaspberryPi-S3-WriteOnly`
7. Click "Create policy"
8. Go back to the user creation tab, refresh policies, and search for `RaspberryPi-S3-WriteOnly`
9. Select the policy and click "Next"

## Step 3: Create Access Keys

1. After user is created, click on the user name
2. Go to "Security credentials" tab
3. Scroll to "Access keys"
4. Click "Create access key"
5. Select "Application running outside AWS"
6. Click "Next"
7. (Optional) Add description: "Raspberry Pi LED Logger"
8. Click "Create access key"
9. **IMPORTANT**: Copy both:
   - Access key ID
   - Secret access key

   You won't be able to see the secret key again!

## Step 4: Configure on Raspberry Pi

Save the credentials in the config file (see `config.example.yaml`)
