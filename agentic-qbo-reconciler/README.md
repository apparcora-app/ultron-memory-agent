# Agentic QBO Reconciler - Proof of Concept

This repository contains a FastAPI service that demonstrates an agentic approach to reconciling bank statements with QuickBooks Online (QBO) transactions.

## Overview

The service provides a `/reconcile` endpoint that accepts CSV files containing bank transactions and returns a reconciliation result, matching each bank transaction with the best possible QBO transaction based on amount and date proximity.

## Key Features

- **CSV Upload**: Accepts bank statement CSV files with columns: `date`, `amount`, `description`
- **Mock QBO Integration**: Uses mock QBO transaction data (in a real implementation, this would be fetched via the QuickBooks API)
- **LLM-based Matching**: Implements a mock LLM matching algorithm that matches bank transactions with QBO transactions based on amount and date proximity
- **FastAPI**: Built with FastAPI for high performance and ease of use
- **Pydantic Models**: Uses Pydantic for data validation and serialization

## Project Structure

```
agentic-qbo-reconciler/
├── main.py
├── requirements.txt
└── README.md
```

## How to Run

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. Clone this repository
2. Navigate to the project directory
3. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Testing the API

You can test the API using curl or a web browser:

#### Upload a CSV file:

```bash
curl -X POST -F "file=@your_bank_statement.csv" http://localhost:8000/reconcile
```

#### View mock QBO data:

```bash
curl http://localhost:8000/qbo-mock
```

## Usage Example

### Sample CSV file (bank_statement.csv):

```csv
date,amount,description
2024-09-01,-150.00,Office Supplies
2024-09-02,2000.00,Client Payment
2024-09-03,-75.50,Utility Bill
```

### Expected API Response:

```json
[
  {
    "bank_transaction": {
      "date": "2024-09-01",
      "amount": -150.0,
      "description": "Office Supplies"
    },
    "qbo_match": {
      "id": "qb1",
      "date": "2024-09-01",
      "amount": -150.0,
      "description": "Office Supplies"
    },
    "status": "matched"
  },
  {
    "bank_transaction": {
      "date": "2024-09-02",
      "amount": 2000.0,
      "description": "Client Payment"
    },
    "qbo_match": {
      "id": "qb2",
      "date": "2024-09-02",
      "amount": 2000.0,
      "description": "Client Payment"
    },
    "status": "matched"
  },
  {
    "bank_transaction": {
      "date": "2024-09-03",
      "amount": -75.5,
      "description": "Utility Bill"
    },
    "qbo_match": {
      "id": "qb3",
      "date": "2024-09-03",
      "amount": -75.5,
      "description": "Utility Bill"
    },
    "status": "matched"
  }
]
```

## Future Enhancements

This is a proof of concept. Future enhancements could include:

- Integration with the actual QuickBooks API
- Use of real LLM services (OpenAI, Claude, etc.) for transaction matching
- Support for more complex edge cases (split payments, refunds, etc.)
- Additional features like anomaly detection and automated exception handling
- Dockerization for easier deployment
- CI/CD pipeline for automated testing and deployment

## License

This project is licensed under the MIT License.