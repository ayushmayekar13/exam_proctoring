# Online Exam Proctoring System

A comprehensive distributed system for conducting online exams with advanced features including cheating detection, time synchronization, mutual exclusion protocols, load balancing, and data replication.

## 🎯 Features

### Core Functionality
- **XML-RPC Client-Server Architecture**: Robust communication between coordinator and student clients
- **Cheating Detection System**: Two-strike system with automatic warnings and termination
- **Berkeley Time Synchronization**: Ensures all student clocks are synchronized with the server
- **Ricart-Agrawala Mutual Exclusion**: Prevents concurrent access to critical sections (marksheet)
- **Conflict Resolution**: Handles simultaneous manual and auto submissions using Lamport timestamps
- **Load Balancing**: Round-robin distribution across multiple server replicas
- **Data Replication**: Master-slave replication with consistency guarantees

### User Interface
- **Teacher Dashboard**: Complete exam control and monitoring interface
- **Student Dashboard**: Real-time status updates and exam interaction
- **Real-time Updates**: Server-sent events for live monitoring
- **Responsive Design**: Bootstrap-based modern UI

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Coordinator   │    │   Replica 1     │
│   (Port 9000)   │◄──►│   (Port 8000)   │◄──►│   (Port 8001)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Student 1     │    │   Student 2     │    │   Student 3     │
│   (Clock +2s)   │    │   (Clock -3s)   │    │   (Clock +5s)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Flask UI      │
                    │   (Port 5000)   │
                    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone or download the project**
   ```bash
   cd exam_proctoring_system
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the system components**

   **Terminal 1 - Main Coordinator Server:**
   ```bash
   python server.py 8000 master
   ```

   **Terminal 2 - Load Balancer:**
   ```bash
   python load_balancer.py 9000
   ```

   **Terminal 3 - Flask Web UI:**
   ```bash
   cd frontend
   python app.py
   ```

4. **Access the system**
   - Open your browser and go to `http://localhost:5000`
   - Use the Teacher Dashboard to register students and start exams
   - Use the Student Dashboard to simulate student behavior

### Running the Demo

**Automated Demo Simulation:**
```bash
python demo_simulation.py
```

This will demonstrate all features including:
- Berkeley time synchronization
- Cheating detection with warnings and termination
- Ricart-Agrawala mutual exclusion
- Conflict resolution for simultaneous submissions
- Load balancing across multiple servers

## 📋 Detailed Setup Instructions

### 1. Starting Multiple Server Replicas

**Master Server (Port 8000):**
```bash
python server.py 8000 master
```

**Replica Servers:**
```bash
# Terminal 2
python server.py 8001 replica1

# Terminal 3  
python server.py 8002 replica2
```

### 2. Starting the Load Balancer

```bash
python load_balancer.py 9000
```

The load balancer will automatically distribute requests across all available servers.

### 3. Starting the Web Interface

```bash
cd frontend
python app.py
```

Navigate to `http://localhost:5000` to access the web interface.

### 4. Running Student Clients

**Individual Student Client:**
```bash
python student_client.py 23102A0001 2.0  # Roll number and clock skew
```

**Multiple Students with Different Clock Skews:**
```bash
python student_client.py 23102A0001 2.0   # +2 seconds
python student_client.py 23102A0002 -3.0  # -3 seconds  
python student_client.py 23102A0003 5.0   # +5 seconds
```

## 🧪 Testing

### Running Unit Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_server.py

# Run with coverage
python -m pytest tests/ --cov=.
```

### Running Integration Tests

```bash
# Start server and load balancer first
python server.py 8000 master &
python load_balancer.py 9000 &

# Run integration tests
python -m pytest tests/ -v
```

## 🔧 Configuration

### Server Configuration

The server can be configured by modifying the `ExamCoordinator` class in `server.py`:

```python
# Time sync interval (seconds)
self.health_check_interval = 30

# Exam duration (seconds) 
duration = 300

# Cheating detection thresholds
first_offense_penalty = 0.5  # 50% mark deduction
```

### Load Balancer Configuration

Modify `load_balancer.py` to add/remove backends:

```python
backends = [
    "http://127.0.0.1:8000",  # Master
    "http://127.0.0.1:8001",  # Replica 1
    "http://127.0.0.1:8002",  # Replica 2
]
```

## 📊 System Features Explained

### 1. Berkeley Time Synchronization

The system implements the Berkeley algorithm to synchronize clocks across all participants:

1. **Time Collection**: Server collects time reports from all students
2. **Offset Calculation**: Calculates average offset from server time
3. **Correction Distribution**: Sends corrections to all participants
4. **Clock Adjustment**: Students apply corrections to their local clocks

**Example Output:**
```
[12:34:56] [INFO] Berkeley sync completed. Average offset: 1.25s
[12:34:56] [INFO] Student Alice: Final offset = 0.75s
[12:34:56] [INFO] Student Bob: Final offset = -1.25s
```

### 2. Ricart-Agrawala Mutual Exclusion

Ensures only one process can access the marksheet at a time:

1. **Request Phase**: Process sends request to all other processes
2. **Reply Phase**: Processes reply if they don't need CS or have higher priority
3. **Grant Phase**: Process enters CS when it receives all replies
4. **Release Phase**: Process releases CS and grants to next in queue

**Message Flow:**
```
S1 -> S2: REQUEST(ts=100, roll=S1)
S1 -> S3: REQUEST(ts=100, roll=S1)
S2 -> S1: REPLY(ts=101, roll=S2)
S3 -> S1: REPLY(ts=102, roll=S3)
S1: ENTER_CS (has all replies)
```

### 3. Conflict Resolution

Handles simultaneous submissions using deterministic ordering:

1. **Lamport Timestamps**: Each event gets a logical timestamp
2. **Lexicographic Ordering**: If timestamps are equal, use roll number ordering
3. **Atomic Operations**: Compare-and-set operations prevent race conditions
4. **Conflict Response**: Loser receives conflict resolution message

**Example:**
```json
{
  "success": false,
  "reason": "conflict_resolved", 
  "winner": "23102A0001",
  "message": "Submission already in progress"
}
```

### 4. Load Balancing

Round-robin distribution with health checking:

1. **Health Monitoring**: Periodic checks of backend availability
2. **Request Distribution**: Round-robin selection of healthy backends
3. **Failover**: Automatic failover to healthy backends
4. **Recovery**: Automatic recovery when backends become healthy

## 🐛 Troubleshooting

### Common Issues

**1. Port Already in Use**
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

**2. Server Not Responding**
- Check if server is running: `ps aux | grep server.py`
- Check server logs in `exam_system.log`
- Verify port availability

**3. Student Client Connection Failed**
- Ensure server is running on correct port
- Check network connectivity
- Verify server URL in client configuration

**4. Load Balancer Issues**
- Ensure all backend servers are running
- Check backend URLs in load balancer configuration
- Verify health check settings

### Log Files

- **Server Logs**: `exam_system.log`
- **Common Log**: `common.txt` (shared events)
- **Flask Logs**: Console output

### Debug Mode

Enable debug logging by modifying the logging level in `server.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance Considerations

### Scalability
- **Horizontal Scaling**: Add more server replicas
- **Load Distribution**: Use multiple load balancers
- **Database**: Replace in-memory storage with persistent database

### Production Deployment
- **Reverse Proxy**: Use NGINX or Apache for production
- **Process Management**: Use systemd or supervisor
- **Monitoring**: Implement health checks and metrics
- **Security**: Add authentication and encryption

## 🔒 Security Considerations

### Current Implementation
- **Input Validation**: All inputs are validated
- **Error Handling**: Comprehensive error handling
- **Logging**: Detailed audit logs

### Production Recommendations
- **Authentication**: Add user authentication
- **Authorization**: Implement role-based access control
- **Encryption**: Use HTTPS for all communications
- **Rate Limiting**: Implement request rate limiting
- **Audit Trails**: Enhanced logging and monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Run the demo simulation to verify functionality
4. Create an issue with detailed logs and steps to reproduce

## 🎓 Educational Value

This project demonstrates:
- **Distributed Systems Concepts**: Clock synchronization, mutual exclusion, consensus
- **Network Programming**: XML-RPC, client-server architecture
- **Concurrency**: Threading, race conditions, deadlock prevention
- **Web Development**: Flask, real-time updates, responsive design
- **Testing**: Unit tests, integration tests, mocking
- **System Design**: Load balancing, replication, failover

Perfect for understanding distributed systems algorithms and their practical implementation!

