import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../state/cart_state.dart';
import '../theme/app_theme.dart';
import 'checkout_screen.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  final ApiService _api = ApiService();
  final ImagePicker _picker = ImagePicker();
  bool _verifyingCard = false;

  Future<void> _scanLoyaltyCard() async {
    if (_verifyingCard) return;
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera),
              title: const Text('Camera'),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Gallery'),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;

    final picked = await _picker.pickImage(source: source, imageQuality: 92);
    if (picked == null) return;

    setState(() => _verifyingCard = true);
    try {
      final result = await _api.verifyFidelityCard(File(picked.path));
      if (!mounted) return;
      final cart = context.read<CartState>();
      if (result.valid && result.discountPercent > 0) {
        cart.applyLoyalty(
          discountPercent: result.discountPercent,
          cardId: result.cardId,
          customerName: result.customerName,
        );
      } else {
        cart.clearLoyalty();
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.message)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Scan carte fidelite echoue: $e')),
      );
    } finally {
      if (mounted) setState(() => _verifyingCard = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartState>();
    final totalBefore = cart.totalPrice;
    final totalAfter = cart.discountedTotalPrice;
    final hasDiscount = cart.loyaltyApplied && cart.loyaltyDiscountPercent > 0;

    return Scaffold(
      appBar: AppBar(title: const Text('Your Cart')),
      body: Column(
        children: [
          if (cart.hasCatalogItems)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF4F6),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFFC8D2)),
              ),
              child: Text(
                cart.useFastCourse
                    ? 'Fast Course active: ${cart.catalogItemsCount}/${CartState.fastCourseMaxItems} items.'
                    : 'Mixed cart detected: queue recommendation will use normal checkout flow.',
                style: const TextStyle(
                  color: AppTheme.primaryRed,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          if (hasDiscount)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFFEFFFF5),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF93E6B6)),
              ),
              child: Text(
                'Carte fidelite validee: -${cart.loyaltyDiscountPercent}%'
                '${cart.loyaltyCustomerName != null ? ' • ${cart.loyaltyCustomerName}' : ''}',
                style: const TextStyle(
                  color: Color(0xFF0B7A43),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          Expanded(
            child: cart.items.isEmpty
                ? const Center(child: Text('Cart is empty. Start scanning products.'))
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: cart.items.length,
                    separatorBuilder: (context, index) => const SizedBox(height: 8),
                    itemBuilder: (_, index) {
                      final item = cart.items[index];
                      return Card(
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.softGray,
                            child: Text('${item.quantity}x'),
                          ),
                          title: Text(item.product.name),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(item.product.brand),
                              if (item.product.isCatalogSource)
                                const Text(
                                  'Catalog item - Fast Course',
                                  style: TextStyle(
                                    color: AppTheme.primaryRed,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                            ],
                          ),
                          trailing: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                '${item.subtotal.toStringAsFixed(2)} TND',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryRed,
                                ),
                              ),
                              IconButton(
                                iconSize: 18,
                                visualDensity: VisualDensity.compact,
                                onPressed: () => cart.removeOne(item),
                                icon: const Icon(Icons.remove_circle_outline),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.06),
                  blurRadius: 12,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    const Text(
                      'Total',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                    ),
                    const Spacer(),
                    if (hasDiscount)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: Text(
                          '${totalBefore.toStringAsFixed(2)}',
                          style: const TextStyle(
                            decoration: TextDecoration.lineThrough,
                            color: Colors.black45,
                          ),
                        ),
                      ),
                    Text(
                      '${totalAfter.toStringAsFixed(2)} TND',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 20,
                        color: AppTheme.primaryRed,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _verifyingCard || cart.items.isEmpty ? null : _scanLoyaltyCard,
                    icon: _verifyingCard
                        ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.badge_outlined),
                    label: Text(hasDiscount ? 'Rescanner carte fidelite' : 'Scanner carte fidelite (-10%)'),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: cart.items.isEmpty
                        ? null
                        : () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => CheckoutScreen(total: totalAfter),
                              ),
                            );
                          },
                    child: const Text('Proceed to Checkout'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

