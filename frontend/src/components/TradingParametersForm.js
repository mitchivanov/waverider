import React, { useState, useEffect } from 'react';
import axios from 'axios';

function TradingParametersForm() {
  const [parameters, setParameters] = useState({
    symbol: '',
    asset_a_funds: 0,
    asset_b_funds: 0,
    grids: 0,
    deviation_threshold: 0,
    trail_price: false,
    only_profitable_trades: false,
  });

  useEffect(() => {
    // Fetch current parameters from the backend
    axios.get('/api/parameters/').then(response => {
      setParameters(response.data);
    });
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setParameters(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    axios.post('/api/parameters/', parameters)
      .then(response => alert('Parameters updated successfully'))
      .catch(error => alert('Error updating parameters'));
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Symbol:</label>
        <input type="text" name="symbol" value={parameters.symbol} onChange={handleChange} />
      </div>
      <div>
        <label>Asset A Funds:</label>
        <input type="number" name="asset_a_funds" value={parameters.asset_a_funds} onChange={handleChange} />
      </div>
      <div>
        <label>Asset B Funds:</label>
        <input type="number" name="asset_b_funds" value={parameters.asset_b_funds} onChange={handleChange} />
      </div>
      <div>
        <label>Grids:</label>
        <input type="number" name="grids" value={parameters.grids} onChange={handleChange} />
      </div>
      <div>
        <label>Deviation Threshold:</label>
        <input type="number" step="0.01" name="deviation_threshold" value={parameters.deviation_threshold} onChange={handleChange} />
      </div>
      <div>
        <label>Trail Price:</label>
        <input type="checkbox" name="trail_price" checked={parameters.trail_price} onChange={handleChange} />
      </div>
      <div>
        <label>Only Profitable Trades:</label>
        <input type="checkbox" name="only_profitable_trades" checked={parameters.only_profitable_trades} onChange={handleChange} />
      </div>
      <button type="submit">Update Parameters</button>
    </form>
  );
}

export default TradingParametersForm;
