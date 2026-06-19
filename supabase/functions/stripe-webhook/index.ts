// Supabase Edge Function — Webhook Stripe
// Reçoit les événements Stripe et met à jour users_meta en conséquence.
//
// Déploiement :
//   supabase functions deploy stripe-webhook --no-verify-jwt
//
// Variables d'env à configurer dans Supabase Dashboard > Functions :
//   STRIPE_WEBHOOK_SECRET  (whsec_...)
//   SUPABASE_SERVICE_ROLE_KEY  (Settings > API > service_role)

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import Stripe from 'https://esm.sh/stripe@14?target=deno';

const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY') ?? '', {
  apiVersion: '2024-04-10',
  httpClient: Stripe.createFetchHttpClient(),
});

const supabase = createClient(
  Deno.env.get('SUPABASE_URL') ?? '',
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
);

serve(async (req) => {
  const signature = req.headers.get('stripe-signature');
  const body = await req.text();
  const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET') ?? '';

  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(body, signature!, webhookSecret);
  } catch (err) {
    console.error('Signature Stripe invalide:', err);
    return new Response('Signature invalide', { status: 400 });
  }

  console.log(`Event reçu : ${event.type}`);

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session;
      const customerEmail = session.customer_email ?? session.customer_details?.email;
      const customerId = session.customer as string;
      const priceId = session.metadata?.price_id ?? '';

      // Détermine le plan selon le prix Stripe
      const plan = priceId.includes('pro') ? 'pro' : 'starter';

      if (customerEmail) {
        // Récupère l'utilisateur Supabase via son email
        const { data: users } = await supabase.auth.admin.listUsers();
        const user = users?.users?.find(u => u.email === customerEmail);

        if (user) {
          await supabase.from('users_meta').upsert({
            id: user.id,
            plan,
            stripe_customer_id: customerId,
            subscription_active: true,
          });
          console.log(`Plan ${plan} activé pour ${customerEmail}`);
        } else {
          console.warn(`Utilisateur introuvable pour l'email : ${customerEmail}`);
        }
      }
      break;
    }

    case 'customer.subscription.deleted':
    case 'customer.subscription.paused': {
      const sub = event.data.object as Stripe.Subscription;
      const customerId = sub.customer as string;

      const { data: meta } = await supabase
        .from('users_meta')
        .select('id')
        .eq('stripe_customer_id', customerId)
        .single();

      if (meta) {
        await supabase.from('users_meta').update({
          plan: 'free',
          subscription_active: false,
        }).eq('id', meta.id);
        console.log(`Abonnement annulé pour customer ${customerId}`);
      }
      break;
    }

    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription;
      const customerId = sub.customer as string;
      const active = sub.status === 'active' || sub.status === 'trialing';

      const { data: meta } = await supabase
        .from('users_meta')
        .select('id')
        .eq('stripe_customer_id', customerId)
        .single();

      if (meta) {
        await supabase.from('users_meta').update({
          subscription_active: active,
        }).eq('id', meta.id);
      }
      break;
    }

    default:
      console.log(`Event ignoré : ${event.type}`);
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
