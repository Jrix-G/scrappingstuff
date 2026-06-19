/**
 * Firebase Cloud Function Gen 2 — Webhook Stripe
 *
 * Reçoit les events Stripe et met à jour Firestore en conséquence.
 *
 * IMPORTANT : nécessite le plan Blaze (pay-as-you-go) pour les appels réseau
 * sortants vers Stripe. Gratuit en pratique sous 2M invocations/mois.
 *
 * Déploiement :
 *   cd firebase/functions
 *   npm install
 *   firebase deploy --only functions:stripeWebhook
 *
 * Variables d'env (firebase functions:config:set ou .env dans functions/) :
 *   STRIPE_SECRET_KEY=sk_live_...
 *   STRIPE_WEBHOOK_SECRET=whsec_...
 */

import { onRequest } from 'firebase-functions/v2/https';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';
import { initializeApp } from 'firebase-admin/app';
import Stripe from 'stripe';

initializeApp();
const db = getFirestore();

export const stripeWebhook = onRequest(async (req, res) => {
  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? '');
  const sig = req.headers['stripe-signature'];

  if (!sig) { res.status(400).send('Signature manquante'); return; }

  let event: Stripe.Event;
  try {
    // req.rawBody est disponible automatiquement dans les Cloud Functions
    event = stripe.webhooks.constructEvent(
      req.rawBody,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET ?? '',
    );
  } catch (err) {
    console.error('Signature Stripe invalide :', err);
    res.status(400).send(`Webhook Error: ${err}`);
    return; // Stripe re-tente sur 4xx/5xx
  }

  console.log(`Event : ${event.type}`);

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session;
        // On stocke l'uid Firebase dans session.metadata.firebaseUID
        // (à passer côté frontend lors de la création du lien Checkout)
        const uid = session.metadata?.firebaseUID;
        const customerId = session.customer as string;
        const plan = session.metadata?.plan ?? 'starter';

        if (uid) {
          await db.doc(`users/${uid}`).set({
            plan,
            stripe_customer_id: customerId,
            subscription_active: true,
            updated_at: FieldValue.serverTimestamp(),
          }, { merge: true });
          console.log(`Plan ${plan} activé pour uid=${uid}`);
        } else {
          console.warn('metadata.firebaseUID manquant — impossible de lier le paiement');
        }
        break;
      }

      case 'customer.subscription.deleted':
      case 'customer.subscription.paused': {
        const sub = event.data.object as Stripe.Subscription;
        const customerId = sub.customer as string;

        const snap = await db.collection('users')
          .where('stripe_customer_id', '==', customerId)
          .limit(1)
          .get();

        if (!snap.empty) {
          await snap.docs[0].ref.update({
            plan: 'free',
            subscription_active: false,
            updated_at: FieldValue.serverTimestamp(),
          });
          console.log(`Abonnement annulé pour customer=${customerId}`);
        }
        break;
      }

      case 'customer.subscription.updated': {
        const sub = event.data.object as Stripe.Subscription;
        const customerId = sub.customer as string;
        const active = sub.status === 'active' || sub.status === 'trialing';

        const snap = await db.collection('users')
          .where('stripe_customer_id', '==', customerId)
          .limit(1)
          .get();

        if (!snap.empty) {
          await snap.docs[0].ref.update({
            subscription_active: active,
            updated_at: FieldValue.serverTimestamp(),
          });
        }
        break;
      }

      default:
        console.log(`Event ignoré : ${event.type}`);
    }

    res.json({ received: true });
  } catch (err) {
    console.error('Erreur traitement webhook :', err);
    res.status(500).send('Erreur serveur');  // Stripe re-tente
  }
});
