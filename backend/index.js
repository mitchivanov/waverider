const http = require('http');

// Create an HTTP server
const server = http.createServer((req, res) => {
  // Set the response HTTP header with HTTP status and Content type
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  
  // Send the response body "Hello, World!"
  res.end('Hello, World!\n');
});

// Define the port number
const PORT = 3000;

// The server listens on port 3000
server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}/`);
});

