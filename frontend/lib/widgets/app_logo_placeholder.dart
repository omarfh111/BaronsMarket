import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class AppLogoPlaceholder extends StatelessWidget {
  const AppLogoPlaceholder({super.key});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: 150,
        height: 44,
        color: Colors.white,
        alignment: Alignment.center,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Image.asset(
            'assets/monoprix_logo.png',
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => const Text(
              'MONOPRIX',
              style: TextStyle(
                color: AppTheme.primaryRed,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.2,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
