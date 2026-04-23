import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/product.dart';
import '../state/cart_state.dart';
import '../theme/app_theme.dart';
import 'camera_screen.dart';
import 'cart_screen.dart';

class PredictionScreen extends StatefulWidget {
  final List<Product> predictions;
  final String imagePath;

  const PredictionScreen({
    super.key,
    required this.predictions,
    required this.imagePath,
  });

  @override
  State<PredictionScreen> createState() => _PredictionScreenState();
}

class _PredictionScreenState extends State<PredictionScreen> {
  int _selectedIndex = 0;
  final AudioPlayer _player = AudioPlayer();

  Product? get selected => widget.predictions.isEmpty
      ? null
      : widget.predictions[
          _selectedIndex.clamp(0, widget.predictions.length - 1).toInt()
        ];

  Future<void> _onConfirm() async {
    final product = selected;
    if (product == null) return;
    context.read<CartState>().addProduct(product);
    try {
      await _player.play(AssetSource('sounds/add_to_cart.mp3'));
    } catch (_) {
      // Optional audio feedback.
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppTheme.primaryRed,
        content: Text('${product.name} added to cart'),
      ),
    );
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const CartScreen()),
      (route) => route.isFirst,
    );
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Predictions')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: widget.predictions.isEmpty
            ? _EmptyPrediction(imagePath: widget.imagePath)
            : Column(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: Image.file(
                      File(widget.imagePath),
                      height: 180,
                      width: double.infinity,
                      fit: BoxFit.cover,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Expanded(
                    child: ListView.separated(
                      itemCount: widget.predictions.length,
                      separatorBuilder: (context, index) => const SizedBox(height: 10),
                      itemBuilder: (_, index) {
                        final p = widget.predictions[index];
                        final active = index == _selectedIndex;
                        return InkWell(
                          onTap: () => setState(() => _selectedIndex = index),
                          borderRadius: BorderRadius.circular(16),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 220),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: active
                                  ? AppTheme.primaryRed.withValues(alpha: 0.08)
                                  : Colors.white,
                              border: Border.all(
                                color: active
                                    ? AppTheme.primaryRed
                                    : Colors.black.withValues(alpha: 0.08),
                                width: active ? 2 : 1,
                              ),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Row(
                              children: [
                                _NetworkProductImage(url: p.image),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        p.name,
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                      Text(
                                        p.brand,
                                        style: const TextStyle(fontSize: 13),
                                      ),
                                      const SizedBox(height: 6),
                                      Text(
                                        '${p.price.toStringAsFixed(2)} TND',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w700,
                                          color: AppTheme.primaryRed,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                if (p.confidence != null)
                                  Text(
                                    '${(p.confidence! * 100).toStringAsFixed(0)}%',
                                    style: const TextStyle(fontWeight: FontWeight.w700),
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (_) => const CameraScreen()),
                            );
                          },
                          icon: const Icon(Icons.close),
                          label: const Text('Reject'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: _onConfirm,
                          icon: const Icon(Icons.check),
                          label: const Text('Confirm'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
      ),
    );
  }
}

class _EmptyPrediction extends StatelessWidget {
  final String imagePath;
  const _EmptyPrediction({required this.imagePath});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.file(
            File(imagePath),
            height: 180,
            width: double.infinity,
            fit: BoxFit.cover,
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'No product matched.',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        const Text('Try scanning again with better lighting and one product only.'),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const CameraScreen()),
            );
          },
          child: const Text('Back to Camera'),
        ),
      ],
    );
  }
}

class _NetworkProductImage extends StatelessWidget {
  final String url;
  const _NetworkProductImage({required this.url});

  @override
  Widget build(BuildContext context) {
    if (url.trim().isEmpty) {
      return Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          color: AppTheme.softGray,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(Icons.image_outlined),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Image.network(
        url,
        width: 64,
        height: 64,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) => Container(
          width: 64,
          height: 64,
          color: AppTheme.softGray,
          child: const Icon(Icons.broken_image_outlined),
        ),
      ),
    );
  }
}
