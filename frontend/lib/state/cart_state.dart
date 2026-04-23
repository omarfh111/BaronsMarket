import 'package:flutter/foundation.dart';

import '../models/product.dart';

class CartState extends ChangeNotifier {
  final Map<String, CartItem> _items = {};

  List<CartItem> get items => _items.values.toList();

  int get totalItems =>
      _items.values.fold<int>(0, (sum, item) => sum + item.quantity);

  double get totalPrice => _items.values.fold<double>(
    0,
    (sum, item) => sum + item.subtotal,
  );

  void addProduct(Product product) {
    final key = '${product.name}_${product.brand}';
    if (_items.containsKey(key)) {
      _items[key]!.quantity += 1;
    } else {
      _items[key] = CartItem(product: product);
    }
    notifyListeners();
  }

  void removeOne(CartItem item) {
    final key = '${item.product.name}_${item.product.brand}';
    if (!_items.containsKey(key)) return;
    final existing = _items[key]!;
    if (existing.quantity <= 1) {
      _items.remove(key);
    } else {
      existing.quantity -= 1;
    }
    notifyListeners();
  }

  void clear() {
    _items.clear();
    notifyListeners();
  }
}

