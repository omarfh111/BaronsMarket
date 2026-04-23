import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'prediction_screen.dart';

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();
  bool _loading = false;
  String? _error;

  Future<void> _captureAndDetect() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final XFile? capture = await _picker.pickImage(source: ImageSource.camera);
      if (capture == null) {
        setState(() => _loading = false);
        return;
      }

      final predictions = await _api.detectProducts(File(capture.path), topK: 3);
      if (!mounted) return;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => PredictionScreen(
            predictions: predictions,
            imagePath: capture.path,
          ),
        ),
      );
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Camera')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.softGray,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                children: [
                  const Icon(Icons.camera_alt_outlined, size: 64),
                  const SizedBox(height: 12),
                  Text(
                    'Capture product image',
                    style: Theme.of(
                      context,
                    ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Take a clear photo of one product for best AI matching.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            if (_loading) ...[
              const SpinKitPulse(color: AppTheme.primaryRed, size: 44),
              const SizedBox(height: 12),
              const Text('Analyzing product...'),
            ] else
              FilledButton.icon(
                onPressed: _captureAndDetect,
                icon: const Icon(Icons.camera),
                label: const Text('Capture & Detect'),
              ),
            if (_error != null) ...[
              const SizedBox(height: 20),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
