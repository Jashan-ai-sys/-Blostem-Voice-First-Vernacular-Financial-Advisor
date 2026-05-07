import os
import json

journey_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "journey_screens")
jsonl_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "journey_screens.jsonl")

# The 11 standard stages mapped chronologically
stages = [
    {
        "id": "journey_001_sim_binding",
        "stage": "sim_binding",
        "screen_title": "SIM Binding",
        "screen_description": "User starts the FD booking journey by completing SIM binding on the device.",
        "user_goal": "Verify SIM/device linkage before proceeding",
        "visible_elements": ["SIM binding prompt", "continue button"],
        "required_inputs": ["mobile verification"],
        "common_questions": ["SIM binding kya hota hai?", "Ye step kyu zaroori hai?"],
        "common_issues": ["SIM not detected", "verification failed"],
        "next_stage": "amount_tenure_selection",
        "keywords": ["sim binding", "device verification", "onboarding"]
    },
    {
        "id": "journey_002_amount_tenure",
        "stage": "amount_tenure_selection",
        "screen_title": "Tenure and Amount Selection",
        "screen_description": "User chooses FD amount and tenure before moving to PAN and Aadhaar verification.",
        "user_goal": "Select investment amount and tenure",
        "visible_elements": ["amount field", "tenure selector", "continue button"],
        "required_inputs": ["amount", "tenure"],
        "common_questions": ["Kitna amount sahi rahega?", "Kaunsa tenure select karu?"],
        "common_issues": ["confused between plans", "wants maturity estimate"],
        "next_stage": "kyc_verification",
        "keywords": ["amount", "tenure", "fd booking"]
    },
    {
        "id": "journey_003_kyc_verification",
        "stage": "kyc_verification",
        "screen_title": "PAN and Aadhaar Verification",
        "screen_description": "User completes KYC by entering PAN and Aadhaar details.",
        "user_goal": "Verify identity to comply with RBI guidelines",
        "visible_elements": ["PAN input field", "Aadhaar input field", "verify button"],
        "required_inputs": ["PAN number", "Aadhaar number"],
        "common_questions": ["PAN mandatory hai kya?", "Aadhaar OTP nahi aa raha"],
        "common_issues": ["Invalid PAN", "OTP delayed"],
        "next_stage": "address_confirmation",
        "keywords": ["kyc", "pan", "aadhaar", "verification"]
    },
    {
        "id": "journey_004_address_confirmation",
        "stage": "address_confirmation",
        "screen_title": "Communication Address Confirmation",
        "screen_description": "User confirms their communication address for the bank records.",
        "user_goal": "Confirm address for communication",
        "visible_elements": ["address fields", "confirm button"],
        "required_inputs": ["address confirmation"],
        "common_questions": ["Address change karna hai", "Aadhaar wala address alag hai"],
        "common_issues": ["cannot edit address"],
        "next_stage": "nominee_selection",
        "keywords": ["address", "communication", "kyc"]
    },
    {
        "id": "journey_005_nominee_selection",
        "stage": "nominee_selection",
        "screen_title": "Nominee Selection",
        "screen_description": "User adds a nominee for the fixed deposit.",
        "user_goal": "Add a nominee for safety",
        "visible_elements": ["nominee name", "relationship", "DOB", "add nominee button"],
        "required_inputs": ["nominee details"],
        "common_questions": ["Nominee add karna zaroori hai?", "Kisko nominee bana sakte hain?"],
        "common_issues": ["nominee minor hai"],
        "next_stage": "bank_addition",
        "keywords": ["nominee", "beneficiary", "safety"]
    },
    {
        "id": "journey_006_bank_addition",
        "stage": "bank_addition",
        "screen_title": "Bank Addition",
        "screen_description": "User adds their bank account details for funding the FD and receiving payouts.",
        "user_goal": "Link a bank account",
        "visible_elements": ["account number", "IFSC", "verify bank button"],
        "required_inputs": ["account details"],
        "common_questions": ["Konsa bank support hota hai?", "UPI add kar sakte hain?"],
        "common_issues": ["IFSC invalid", "account verification failed"],
        "next_stage": "fd_review",
        "keywords": ["bank account", "ifsc", "payout account"]
    },
    {
        "id": "journey_007_fd_review",
        "stage": "fd_review",
        "screen_title": "FD Review Screen",
        "screen_description": "User reviews all FD details before making the final payment.",
        "user_goal": "Review investment details",
        "visible_elements": ["maturity amount", "interest rate", "tenure", "pay button"],
        "required_inputs": ["confirmation to pay"],
        "common_questions": ["Maturity amount kam kyu dikh raha hai?", "Terms and conditions kya hain?"],
        "common_issues": ["wants to change amount"],
        "next_stage": "payment_processing",
        "keywords": ["review", "summary", "confirm"]
    },
    {
        "id": "journey_008_payment_status",
        "stage": "payment_processing",
        "screen_title": "Payment Status",
        "screen_description": "Screen showing the status of the FD payment transaction.",
        "user_goal": "Confirm payment success",
        "visible_elements": ["payment success/fail indicator", "transaction ID"],
        "required_inputs": [],
        "common_questions": ["Paisa kat gaya par FD nahi bani", "Kitna time lagta hai payment hone mein?"],
        "common_issues": ["payment failed", "amount debited but pending"],
        "next_stage": "video_kyc",
        "keywords": ["payment", "transaction", "status", "upi", "netbanking"]
    },
    {
        "id": "journey_009_video_kyc",
        "stage": "video_kyc",
        "screen_title": "Video KYC Journey",
        "screen_description": "User completes Video KYC with a bank agent to fully activate the account.",
        "user_goal": "Complete full KYC via video call",
        "visible_elements": ["start video call button", "agent connection screen"],
        "required_inputs": ["camera access", "microphone access", "original PAN card"],
        "common_questions": ["Video KYC kitne baje tak hota hai?", "Original PAN nahi hai toh kya karu?"],
        "common_issues": ["call drops", "agent not available"],
        "next_stage": "active_fd",
        "keywords": ["vkyc", "video call", "full kyc"]
    },
    {
        "id": "journey_010_active_fd",
        "stage": "active_fd",
        "screen_title": "Active FD Dashboard",
        "screen_description": "User views their successfully created active FD on the dashboard.",
        "user_goal": "View active investment",
        "visible_elements": ["current balance", "maturity date", "interest earned", "withdraw button"],
        "required_inputs": [],
        "common_questions": ["Interest kab credit hoga?", "Certificate kahan se download karu?"],
        "common_issues": ["dashboard not updating"],
        "next_stage": "premature_withdrawal",
        "keywords": ["dashboard", "active", "portfolio", "receipt"]
    },
    {
        "id": "journey_011_premature_withdrawal",
        "stage": "premature_withdrawal",
        "screen_title": "Premature Withdrawal",
        "screen_description": "User requests to break the FD before maturity, verifying with Aadhaar OTP.",
        "user_goal": "Withdraw funds early",
        "visible_elements": ["withdrawal amount", "penalty details", "OTP input"],
        "required_inputs": ["OTP"],
        "common_questions": ["FD todne pe kitna penalty lagega?", "Paisa kitne din mein account mein aayega?"],
        "common_issues": ["OTP nahi aaya", "withdrawal stuck"],
        "next_stage": "closed",
        "keywords": ["withdraw", "break fd", "penalty", "otp"]
    }
]

def main():
    if not os.path.exists(journey_dir):
        print(f"Directory {journey_dir} not found.")
        return
        
    files = [f for f in os.listdir(journey_dir) if f.endswith(".png")]
    
    # Sort files chronologically based on filename (since names contain date/time)
    # The filenames are like 'ChatGPT Image May 4, 2026, 04_34_36 PM.png'
    # Since they are generated sequentially on the same day, sorting by filename strings
    # might be tricky due to AM/PM and string comparison, but let's sort by actual creation/mod time.
    files_with_time = [(f, os.path.getmtime(os.path.join(journey_dir, f))) for f in files]
    files_with_time.sort(key=lambda x: x[1])
    
    sorted_files = [f[0] for f in files_with_time]
    
    if len(sorted_files) != len(stages):
        print(f"Warning: Found {len(sorted_files)} images, but expected {len(stages)} stages.")
    
    with open(jsonl_path, 'w') as f_out:
        for i, stage_data in enumerate(stages):
            if i < len(sorted_files):
                old_name = sorted_files[i]
                new_name = f"{stage_data['stage']}.png"
                old_path = os.path.join(journey_dir, old_name)
                new_path = os.path.join(journey_dir, new_name)
                
                # Rename the file
                os.rename(old_path, new_path)
                
                # Add to jsonl
                stage_data["page_number"] = i + 1
                stage_data["image_path"] = f"data/journey_screens/{new_name}"
                
                f_out.write(json.dumps(stage_data) + "\n")
                print(f"Mapped {old_name} -> {new_name}")

if __name__ == "__main__":
    main()
