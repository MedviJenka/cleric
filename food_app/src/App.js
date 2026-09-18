import { useMemo, useState } from 'react';
import './App.css';

const restaurants = [
  {
    name: 'Green Bowl Bistro',
    cuisine: 'Salads, bowls, smoothies',
    rating: '4.9',
    eta: '20-30 min',
  },
  {
    name: 'Tandoori Trail',
    cuisine: 'North Indian comfort food',
    rating: '4.8',
    eta: '25-35 min',
  },
  {
    name: 'Slice Society',
    cuisine: 'Wood-fired pizza',
    rating: '4.7',
    eta: '18-28 min',
  },
];

const menuItems = [
  {
    name: 'Pesto Panini',
    restaurant: 'Green Bowl Bistro',
    description: 'Toasted focaccia, basil pesto, mozzarella, roasted tomatoes.',
    price: 12.5,
  },
  {
    name: 'Mango Lassi',
    restaurant: 'Tandoori Trail',
    description: 'Creamy yogurt drink blended with alphonso mango and cardamom.',
    price: 10,
  },
  {
    name: 'Margherita Pizza',
    restaurant: 'Slice Society',
    description: 'San Marzano tomatoes, fresh mozzarella, basil, olive oil.',
    price: 14,
  },
];

const formatCurrency = (amount) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);

function App() {
  const [cart, setCart] = useState([]);
  const [address, setAddress] = useState('');

  const subtotal = useMemo(
    () => cart.reduce((total, item) => total + item.price, 0),
    [cart]
  );
  const deliveryFee = cart.length > 0 ? 3.99 : 0;
  const total = subtotal + deliveryFee;
  const trimmedAddress = address.trim();
  const canPlaceOrder = cart.length > 0 && trimmedAddress.length > 0;

  const addToCart = (item) => {
    setCart((currentCart) => [...currentCart, item]);
  };

  return (
    <main className="app-shell">
      <section className="hero" aria-labelledby="hero-heading">
        <div className="hero-copy">
          <p className="eyebrow">Dinner without the detour</p>
          <h1 id="hero-heading">Fresh food, fast delivery</h1>
          <p className="hero-text">
            Order from hand-picked local favorites and track a curated meal from
            kitchen to doorstep.
          </p>
          <div className="hero-actions">
            <a href="#menu" className="primary-action">
              Browse menu
            </a>
            <span className="delivery-promise">Average delivery: 25-35 min</span>
          </div>
        </div>

        <aside className="hero-card" aria-label="Live delivery status">
          <span className="status-pill">Live</span>
          <h2>Tonight's fastest lane</h2>
          <p>Tandoori Trail has drivers nearby and hot orders leaving now.</p>
          <strong>25-35 min</strong>
        </aside>
      </section>

      <section className="restaurants" aria-labelledby="restaurants-heading">
        <div className="section-heading">
          <p className="eyebrow">Local favorites</p>
          <h2 id="restaurants-heading">Featured restaurants</h2>
        </div>
        <div className="restaurant-grid">
          {restaurants.map((restaurant) => (
            <article className="restaurant-card" key={restaurant.name}>
              <div>
                <h3>{restaurant.name}</h3>
                <p>{restaurant.cuisine}</p>
              </div>
              <dl>
                <div>
                  <dt>Rating</dt>
                  <dd>{restaurant.rating}</dd>
                </div>
                <div>
                  <dt>ETA</dt>
                  <dd>{restaurant.eta}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="ordering-grid" aria-label="Menu and checkout">
        <div className="menu-panel" id="menu">
          <div className="section-heading">
            <p className="eyebrow">Popular now</p>
            <h2>Build your order</h2>
          </div>
          <div className="menu-list">
            {menuItems.map((item) => (
              <article className="menu-item" key={item.name}>
                <div>
                  <span>{item.restaurant}</span>
                  <h3>{item.name}</h3>
                  <p>{item.description}</p>
                </div>
                <div className="menu-item-action">
                  <strong>{formatCurrency(item.price)}</strong>
                  <button type="button" onClick={() => addToCart(item)}>
                    Add {item.name}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="cart-panel" aria-labelledby="cart-heading">
          <div className="section-heading">
            <p className="eyebrow">Checkout</p>
            <h2 id="cart-heading">Your order</h2>
          </div>

          <div className="cart-summary" aria-live="polite">
            <span>{cart.length} {cart.length === 1 ? 'item' : 'items'}</span>
            <strong>{formatCurrency(subtotal)}</strong>
          </div>

          {cart.length === 0 ? (
            <p className="empty-cart">Add a dish to start your delivery.</p>
          ) : (
            <ul className="cart-items">
              {cart.map((item, index) => (
                <li key={`${item.name}-${index}`}>
                  <span>{item.name}</span>
                  <span>{formatCurrency(item.price)}</span>
                </li>
              ))}
            </ul>
          )}

          <label className="address-field" htmlFor="delivery-address">
            Delivery address
            <input
              id="delivery-address"
              type="text"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              placeholder="123 Market Street"
            />
          </label>

          <p className="delivery-note">
            {trimmedAddress
              ? `Delivering to ${trimmedAddress}`
              : 'Add an address to unlock checkout.'}
          </p>

          <div className="totals">
            <span>Delivery fee</span>
            <strong>{formatCurrency(deliveryFee)}</strong>
            <span>Total</span>
            <strong>{formatCurrency(total)}</strong>
          </div>

          <button className="checkout-button" type="button" disabled={!canPlaceOrder}>
            Place order
          </button>
        </aside>
      </section>
    </main>
  );
}

export default App;
