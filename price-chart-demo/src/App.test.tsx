import React from 'react';
import { render } from '@testing-library/react';
import App from './App';

test('renders price chart demo heading', () => {
  const { getByText } = render(<App />);
  const headingElement = getByText(/Price Chart Demo/i);
  expect(headingElement).toBeInTheDocument();
});