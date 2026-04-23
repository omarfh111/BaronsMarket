import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/home_screen.dart';
import 'state/cart_state.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SmartShoppingApp());
}

class SmartShoppingApp extends StatelessWidget {
  const SmartShoppingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => CartState(),
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Smart Shopping Assistant',
        theme: AppTheme.lightTheme(),
        home: const HomeScreen(),
      ),
    );
  }
}

