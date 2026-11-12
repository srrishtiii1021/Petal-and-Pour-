const cart = new Map();
const $ = (id) => document.getElementById(id);
const items = () => [...cart.values()];
const totalRupees = () => items().reduce((sum, item) => sum + item.price * item.quantity, 0);
function renderCart() {
  const count = items().reduce((sum, item) => sum + item.quantity, 0);
  $('cartCount').textContent = `${count} item${count === 1 ? '' : 's'}`;
  $('cartTotal').textContent = totalRupees();
  $('modalTotal').textContent = totalRupees();
  $('orderSummary').innerHTML = items().map(i => `<div class="order-line"><span>${i.name} × ${i.quantity}</span><b>₹${i.price * i.quantity}</b></div>`).join('') || '<p>Your cart is empty.</p>';
}
document.querySelectorAll('.add-btn').forEach(btn => btn.addEventListener('click', () => {
  const id = Number(btn.dataset.id), old = cart.get(id);
  cart.set(id, {id, name: btn.dataset.name, price: Number(btn.dataset.price), quantity: old ? old.quantity + 1 : 1});
  renderCart(); btn.innerHTML = 'Added <span>✓</span>'; setTimeout(() => btn.innerHTML = 'Add to order <span>+</span>', 800);
}));
$('filters').addEventListener('click', e => {
  const b = e.target.closest('[data-filter]'); if (!b) return;
  document.querySelectorAll('.filter').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('.menu-card').forEach(c => c.hidden = b.dataset.filter !== 'All' && c.dataset.category !== b.dataset.filter);
});
$('checkoutBtn').addEventListener('click', () => {
  if (!cart.size) { alert('Add something delicious to your order first.'); return; }
  renderCart(); $('checkoutModal').classList.add('show'); $('checkoutModal').setAttribute('aria-hidden', 'false');
});
function closeModal() { $('checkoutModal').classList.remove('show'); $('checkoutModal').setAttribute('aria-hidden', 'true'); }
$('closeModal').addEventListener('click', closeModal);
$('checkoutModal').addEventListener('click', e => { if (e.target === $('checkoutModal')) closeModal(); });
$('orderForm').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = $('orderMessage'), btn = e.currentTarget.querySelector('button[type="submit"]');
  const name = $('orderName').value.trim(), phone = $('orderPhone').value.trim();
  btn.disabled = true; msg.textContent = 'Creating secure payment…';
  try {
    const response = await fetch('/api/orders/create', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify({name, phone, items: items().map(({id, quantity}) => ({id, quantity}))})
    });
    const order = await response.json();
    if (!response.ok) throw new Error(order.error || 'Unable to create payment order.');
    const options = {
      key: order.key_id, amount: order.amount, currency: order.currency,
      name: order.cafe_name, description: 'Petal & Pour cafe order',
      order_id: order.razorpay_order_id,
      prefill: {name: order.customer_name, contact: order.customer_phone},
      theme: {color: '#71866e'},
      handler: async function (payment) {
        msg.textContent = 'Verifying payment securely…';
        const verifyResponse = await fetch('/api/payments/verify', {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
          body: JSON.stringify(payment)
        });
        const verified = await verifyResponse.json();
        if (!verifyResponse.ok || !verified.ok) { msg.textContent = verified.error || 'Payment verification failed. Contact the cafe before retrying.'; return; }
        msg.textContent = verified.message + ` Order #${verified.order_id}.`;
        cart.clear(); renderCart(); e.currentTarget.reset();
      },
      modal: {ondismiss: function () { msg.textContent = 'Checkout closed. If you completed payment, please wait for confirmation or contact the cafe.'; }}
    };
    const checkout = new Razorpay(options);
    checkout.on('payment.failed', response => { msg.textContent = response.error.description || 'Payment failed. Please try again.'; });
    checkout.open();
  } catch (err) { msg.textContent = err.message; }
  finally { btn.disabled = false; btn.innerHTML = 'Pay securely · ₹<span id="modalTotal">' + totalRupees() + '</span>'; }
});
$('menuToggle').addEventListener('click', () => $('nav').classList.toggle('open'));
document.querySelectorAll('#nav a').forEach(a => a.addEventListener('click', () => $('nav').classList.remove('open')));
$('year').textContent = new Date().getFullYear();
const dateInput = $('reservationDate');
if (dateInput) { const d = new Date(); dateInput.min = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
renderCart();
