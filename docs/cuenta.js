/* ---------- cuenta: inicio de sesión con correo y lista de deseos sincronizada (Firebase) ---------- */
import { initializeApp, getAuth, onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword,
         sendPasswordResetEmail, signOut, getFirestore, doc, onSnapshot, setDoc, serverTimestamp } from './firebase.js';

const app = initializeApp({
  apiKey: "AIzaSyCydE-tbOVK0poYLFQZQF0i2ZkVy62lqoE",
  authDomain: "figuratodo.firebaseapp.com",
  projectId: "figuratodo",
  storageBucket: "figuratodo.firebasestorage.app",
  messagingSenderId: "639152624887",
  appId: "1:639152624887:web:59e768c54d5bbd47a3aff2"
});
const auth = getAuth(app); auth.languageCode = 'es';
const db = getFirestore(app);

let user = null, unsub = null, pushT = null, applying = false, pendingLocal = false, ready = false;
const msg = (t, ok) => { const m = $('#accMsg'); m.textContent = t || ''; m.className = 'accmsg' + (t ? (ok ? ' ok' : ' err') : ''); };
const ERR = {
  'auth/invalid-credential': 'Correo o contraseña incorrectos.', 'auth/wrong-password': 'Correo o contraseña incorrectos.',
  'auth/user-not-found': 'No hay una cuenta con ese correo. Usa "Crear cuenta".', 'auth/invalid-email': 'Ese correo no es válido.',
  'auth/missing-password': 'Escribe tu contraseña.', 'auth/weak-password': 'La contraseña debe tener al menos 6 caracteres.',
  'auth/email-already-in-use': 'Ya existe una cuenta con ese correo. Usa "Entrar".',
  'auth/too-many-requests': 'Demasiados intentos. Espera unos minutos y vuelve a probar.',
  'auth/network-request-failed': 'Sin conexión. Revisa tu internet.',
  'auth/unauthorized-domain': 'Este sitio no está autorizado en Firebase (Authentication → Configuración → Dominios autorizados).',
  'auth/operation-not-allowed': 'El inicio con correo y contraseña no está activado en Firebase.',
  'permission-denied': 'La base de datos rechazó el acceso: faltan las reglas de Firestore.',
};
const errText = e => ERR[e?.code] || 'No se pudo completar' + (e?.code ? ` (${e.code}).` : '.');

// recuerda que hay sesión para cargar este módulo apenas se abra el sitio la próxima vez
const u2flag = () => { if (user) localStorage.setItem('ft_acc', '1'); else localStorage.removeItem('ft_acc'); };

/* --- ventana de cuenta --- */
export const openAcc = () => { msg(''); $('#accOv').classList.add('on'); if (!user) setTimeout(() => $('#accMail').focus(), 50); };
const closeAcc = () => $('#accOv').classList.remove('on');
$('#accX').onclick = closeAcc;
$('#accOv').onclick = e => { if (e.target.id === 'accOv') closeAcc(); };
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAcc(); });
const creds = () => [$('#accMail').value.trim(), $('#accPass').value];
async function run(btn, fn){
  btn.disabled = true; msg('');
  try { await fn(); } catch (e) { msg(errText(e)); } finally { btn.disabled = false; }
}
$('#accForm').onsubmit = e => { e.preventDefault(); run($('#accLogin'), () => signInWithEmailAndPassword(auth, ...creds())); };
$('#accNew').onclick = () => run($('#accNew'), () => createUserWithEmailAndPassword(auth, ...creds()));
$('#accReset').onclick = () => run($('#accReset'), async () => {
  const mail = creds()[0];
  if (!mail) { msg('Escribe tu correo arriba y vuelve a tocar "Olvidé mi contraseña".'); return; }
  await sendPasswordResetEmail(auth, mail);
  msg('Si existe una cuenta con ese correo, te llegará un email para crear una nueva contraseña. Revisa también spam.', true);
});
$('#accLogout').onclick = () => run($('#accLogout'), () => signOut(auth));

function showUser(){
  try { u2flag(); } catch (e) {}
  $('#accBtn').hidden = false;
  $('#accBtn').textContent = user ? '● ' + user.email : 'Iniciar sesión';
  $('#accBtn').title = user ? 'Tu cuenta' : 'Inicia sesión para sincronizar tu lista de deseos';
  $('#accIn').hidden = !!user; $('#accOut').hidden = !user;
  if (user) { $('#accWho').textContent = user.email; $('#accPass').value = ''; }
  $('#wlInfo').textContent = user
    ? `Tu lista se guarda en tu cuenta (${user.email}) y se ve igual en todos tus dispositivos.`
    : 'La lista se guarda en este navegador. Inicia sesión para verla en cualquier dispositivo, o usa "Copiar lista" y pégala allá.';
}

/* --- sincronización de la lista --- */
const ref = () => doc(db, 'users', user.uid);
async function push(){
  if (!user) return;
  pendingLocal = false;
  try {
    await setDoc(ref(), {items: WL.slice(0, 2000), updated: serverTimestamp()});
    localStorage.setItem('ft_wl_sync', user.uid);
  } catch (e) { $('#wlInfo').textContent = 'No se pudo guardar la lista en tu cuenta: ' + errText(e); }
}
window.wlSync = () => {
  if (applying) return;
  if (!user) { try { localStorage.removeItem('ft_wl_sync'); } catch (e) {} return; }
  if (!ready) return; // todavía no llega la lista de la cuenta: se juntará al llegar
  pendingLocal = true; clearTimeout(pushT); pushT = setTimeout(push, 400);
};
function useList(items){
  applying = true; WL = wlClean(items); wlSave(); applying = false;
  try { localStorage.setItem('ft_wl_sync', user.uid); } catch (e) {}
  if (!$('#vWl').hidden) drawWl();
  wlRemap();
}

onAuthStateChanged(auth, u => {
  user = u;
  if (unsub) { unsub(); unsub = null; }
  clearTimeout(pushT); pendingLocal = false; ready = false;
  showUser();
  if (!u) return;
  closeAcc();
  let first = true;
  unsub = onSnapshot(ref(), snap => {
    if (snap.metadata.hasPendingWrites || pendingLocal) return;
    const remote = snap.exists() && Array.isArray(snap.data().items) ? snap.data().items : null;
    if (first) {
      first = false; ready = true;
      // si esta lista ya estaba sincronizada con la cuenta y no se tocó sin sesión, manda la cuenta;
      // si no, se juntan las dos para no perder nada
      const synced = localStorage.getItem('ft_wl_sync') === u.uid;
      const list = remote ? (synced ? remote : wlMerge(WL, remote)) : WL;
      useList(list);
      if (!remote || !synced) push();
      return;
    }
    if (remote) useList(remote);
  }, e => { $('#wlInfo').textContent = 'No se pudo leer tu lista desde la cuenta: ' + errText(e); });
});
