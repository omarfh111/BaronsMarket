import 'dart:io';

import 'package:flutter/material.dart';

import '../models/meat_freshness_result.dart';
import '../theme/app_theme.dart';
import 'camera_screen.dart';

class MeatFreshnessResultScreen extends StatelessWidget {
  final MeatFreshnessResult result;
  final String imagePath;
  final String freshnessType;

  const MeatFreshnessResultScreen({
    super.key,
    required this.result,
    required this.imagePath,
    this.freshnessType = 'meat',
  });

  Color _labelColor(String label) {
    if (label == 'Healthy') return Colors.green;
    if (label == 'Rotten') return Colors.red;
    switch (label) {
      case 'Fresh':
        return Colors.green;
      case 'Half-Fresh':
        return Colors.orange;
      case 'Spoiled':
        return Colors.red;
      default:
        return AppTheme.primaryRed;
    }
  }

  @override
  Widget build(BuildContext context) {
    final sorted = result.probabilities.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final isVegetable = freshnessType == 'vegetable';

    return Scaffold(
      appBar: AppBar(title: Text(isVegetable ? 'Vegetable Freshness Result' : 'Meat Freshness Result')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.file(
                File(imagePath),
                height: 190,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.black.withValues(alpha: 0.08)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Prediction',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    result.label,
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      color: _labelColor(result.label),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Confidence: ${(result.confidence * 100).toStringAsFixed(1)}%',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.black.withValues(alpha: 0.08)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Class probabilities',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 12),
                    ...sorted.map((entry) {
                      final pct = (entry.value * 100).clamp(0, 100);
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${entry.key}: ${pct.toStringAsFixed(1)}%',
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 6),
                            LinearProgressIndicator(
                              value: (entry.value).clamp(0, 1),
                              minHeight: 9,
                              borderRadius: BorderRadius.circular(99),
                              color: _labelColor(entry.key),
                              backgroundColor: Colors.black.withValues(alpha: 0.08),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  Navigator.pushAndRemoveUntil(
                    context,
                    MaterialPageRoute(
                      builder: (_) => CameraScreen(
                        meatFreshnessMode: !isVegetable,
                        vegetableFreshnessMode: isVegetable,
                      ),
                    ),
                    (route) => route.isFirst,
                  );
                },
                icon: const Icon(Icons.camera_alt_outlined),
                label: Text(isVegetable ? 'Scan another vegetable image' : 'Scan another meat image'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
