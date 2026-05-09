import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../models/assistant_chat.dart';
import '../models/checkout_save.dart';
import '../services/api_service.dart';
import '../state/cart_state.dart';
import '../theme/app_theme.dart';

class CheckoutScreen extends StatefulWidget {
  final double total;
  const CheckoutScreen({super.key, required this.total});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String _queueLabel = 'N/A';
  CheckoutSaveResponse? _saveResult;
  String? _saveError;

  @override
  void initState() {
    super.initState();
    _prepareCheckout();
  }

  List<AssistantCartItemPayload> _toPayload(CartState cart) {
    return cart.items
        .map(
          (item) => AssistantCartItemPayload(
            name: item.product.name,
            brand: item.product.brand,
            quantity: item.quantity,
            unitPrice: item.product.price,
          ),
        )
        .toList();
  }

  Future<void> _prepareCheckout() async {
    final cart = context.read<CartState>();
    String queue = cart.useFastCourse ? 'Fast Course' : 'N/A';

    if (!cart.useFastCourse) {
      try {
        final latest = await _api.getLatestQueueRecommendation();
        queue = latest.bestQueue;
      } catch (_) {
        queue = 'N/A';
      }
    }

    CheckoutSaveResponse? saveResult;
    String? saveError;
    try {
      saveResult = await _api.saveCheckout(
        cartId: cart.cartId,
        createdAtUnixMs: cart.createdAtUnixMs,
        recommendedQueue: queue,
        totalPrice: widget.total,
        items: _toPayload(cart),
        metadata: {
          'source': 'mobile_checkout',
          'loyalty_applied': cart.loyaltyApplied,
          'loyalty_discount_percent': cart.loyaltyDiscountPercent,
          'loyalty_card_id': cart.loyaltyCardId,
          'loyalty_customer_name': cart.loyaltyCustomerName,
        },
      );
    } catch (e) {
      saveError = e.toString();
    }

    if (!mounted) return;
    setState(() {
      _queueLabel = queue;
      _saveResult = saveResult;
      _saveError = saveError;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final payload =
        'smart-shopping-assistant|total=${widget.total.toStringAsFixed(2)}|checkout=$_queueLabel';

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Center(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Final Bill',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${widget.total.toStringAsFixed(2)} TND',
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.primaryRed,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_loading)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: Text('Preparing checkout...'),
                    )
                  else
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        'Recommended checkout: $_queueLabel',
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          color: AppTheme.primaryRed,
                        ),
                      ),
                    ),
                  if (_saveResult != null)
                    Text(
                      'Cart saved: ${_saveResult!.cartId} | Duration: ${_saveResult!.durationSeconds ?? 0}s | Storage: ${_saveResult!.storedIn}',
                      style: const TextStyle(fontSize: 12, color: Colors.black54),
                      textAlign: TextAlign.center,
                    ),
                  if (_saveError != null)
                    Text(
                      'Save warning: $_saveError',
                      style: const TextStyle(fontSize: 12, color: Colors.orange),
                      textAlign: TextAlign.center,
                    ),
                  const SizedBox(height: 14),
                  QrImageView(
                    data: payload,
                    size: 220,
                    backgroundColor: Colors.white,
                    eyeStyle: const QrEyeStyle(
                      eyeShape: QrEyeShape.square,
                      color: AppTheme.primaryRed,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Show this QR code at checkout',
                    style: TextStyle(fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.tonal(
                      onPressed: () {
                        context.read<CartState>().clear();
                        Navigator.popUntil(context, (route) => route.isFirst);
                      },
                      child: const Text('Complete & Clear Cart'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

