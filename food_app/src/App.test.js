import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

test('renders the food delivery landing experience', () => {
  render(<App />);

  expect(
    screen.getByRole('heading', { name: /fresh food, fast delivery/i })
  ).toBeInTheDocument();
  expect(screen.getByText(/order from hand-picked local favorites/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Green Bowl Bistro/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Tandoori Trail/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Slice Society/i })).toBeInTheDocument();
});

test('lets customers build a cart and prepare checkout', () => {
  render(<App />);

  const checkoutButton = screen.getByRole('button', { name: /place order/i });
  expect(checkoutButton).toBeDisabled();

  userEvent.click(screen.getByRole('button', { name: /add pesto panini/i }));
  userEvent.click(screen.getByRole('button', { name: /add mango lassi/i }));

  expect(screen.getByText(/2 items/i)).toBeInTheDocument();
  expect(screen.getByText(/\$22\.50/)).toBeInTheDocument();

  userEvent.type(screen.getByLabelText(/delivery address/i), '123 Market Street');

  expect(checkoutButton).toBeEnabled();
  expect(screen.getByText(/Delivering to 123 Market Street/i)).toBeInTheDocument();
});
