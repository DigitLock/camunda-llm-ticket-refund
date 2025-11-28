#!/usr/bin/env python3
"""
OpenAI-powered Camunda External Task Worker
Analyzes fare rules for ticket refund processing
"""

import os
import sys
import logging
from camunda.external_task.external_task_worker import ExternalTaskWorker
from camunda.external_task.external_task import ExternalTask, TaskResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CAMUNDA_URL = "http://localhost:8080/engine-rest"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable not set!")
    sys.exit(1)

def analyze_fare_rules(task: ExternalTask) -> TaskResult:
    """
    Uses GPT-4 to analyze fare rules and determine refund eligibility
    """
    # Import OpenAI inside function to avoid init issues
    from openai import OpenAI
    
    # Get process variables
    booking_id = task.get_variable("bookingId") or "DEMO-" + str(task.get_task_id())[:8]
    ticket_class = task.get_variable("ticketClass") or "Economy"
    
    logger.info(f"Processing booking {booking_id}, class: {ticket_class}")
    
    # Prepare prompt for GPT
    prompt = f"""You are an airline refund policy expert. Analyze this ticket refund request:

Booking ID: {booking_id}
Ticket Class: {ticket_class}
Purchase Date: 2025-01-15
Flight Date: 2025-03-20
Days until flight: 54
Airline: Standard International Carrier

Based on typical airline refund policies, determine the refund category:
- ALLOWED: Full refund with no penalty (flexible tickets, cancellation within 24h, etc.)
- WITH_PENALTY: Refund possible but with cancellation fee
- MANUAL: Requires human review (edge cases, special circumstances, group bookings)

Respond with ONLY ONE WORD: ALLOWED, WITH_PENALTY, or MANUAL"""

    try:
        # Initialize client per request
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Call OpenAI API
        logger.info("Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an airline policy expert. Respond with only one word."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.3
        )
        
        # Parse response
        decision = response.choices[0].message.content.strip().upper()
        
        # Validate decision
        valid_decisions = ["ALLOWED", "WITH_PENALTY", "MANUAL"]
        if decision not in valid_decisions:
            logger.warning(f"Invalid decision '{decision}', defaulting to MANUAL")
            decision = "MANUAL"
        
        logger.info(f"GPT decision: {decision}")
        
        # Return TaskResult with variables
        return task.complete({
            "fareRuleCheck": decision,
            "llmProvider": "OpenAI GPT-4o-mini",
            "llmReasoning": f"AI analysis for {booking_id}",
            "apiErrorCount": 0
        })
        
    except Exception as e:
        logger.error(f"OpenAI API Error: {e}")
        # Return failure with manual review fallback
        return task.complete({
            "fareRuleCheck": "MANUAL",
            "llmError": str(e),
            "apiErrorCount": 0
        })

def main():
    logger.info("Starting LLM External Task Worker...")
    logger.info(f"Connecting to Camunda: {CAMUNDA_URL}")
    
    worker = ExternalTaskWorker(
        worker_id="llm-fare-analyzer-1",
        base_url=CAMUNDA_URL,
        config={
            "maxTasks": 1,
            "lockDuration": 30000,
            "asyncResponseTimeout": 10000,
        }
    )
    
    worker.subscribe("analyze-fare-rules", analyze_fare_rules)
    logger.info("Worker started successfully! Listening for tasks...")

if __name__ == "__main__":
    main()
