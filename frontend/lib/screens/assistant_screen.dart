import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/assistant_chat.dart';
import '../models/product.dart';
import '../services/api_service.dart';
import '../state/cart_state.dart';
import '../theme/app_theme.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final ApiService _api = ApiService();
  final TextEditingController _messageController = TextEditingController();
  final List<_ChatBubble> _messages = [];

  String? _sessionId;
  String _activeAgent = 'general';
  bool _sending = false;

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  List<AssistantCartItemPayload> _cartPayload(CartState cart) {
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

  double? _extractBudgetFromText(String text) {
    final normalized = text.replaceAll(',', '.').toLowerCase();
    final hasBudgetHint = RegExp(r'\b(budget|tnd|dt|dinar)\b').hasMatch(normalized);
    if (!hasBudgetHint) return null;

    final match = RegExp(
      r'(\d+(?:\.\d+)?)\s*(tnd|dt|dinar)?',
      caseSensitive: false,
    ).firstMatch(normalized);
    if (match == null) return null;
    return double.tryParse(match.group(1) ?? '');
  }

  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty || _sending) return;

    setState(() {
      _sending = true;
      _messages.add(_ChatBubble.user(text));
      _messageController.clear();
    });

    final cart = context.read<CartState>();
    try {
      final response = await _api.sendAssistantMessage(
        message: text,
        sessionId: _sessionId,
        budgetTnd: _extractBudgetFromText(text),
        cartItems: _cartPayload(cart),
      );
      if (!mounted) return;
      setState(() {
        _sessionId = response.sessionId;
        _activeAgent = response.activeAgent;
        _messages.add(_ChatBubble.assistant(response));
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatBubble.assistantError('Erreur: $e'));
      });
    } finally {
      if (mounted) {
        setState(() {
          _sending = false;
        });
      }
    }
  }

  void _addRecommendationToCart(AssistantRecommendedProduct p) {
    final cart = context.read<CartState>();
    final product = Product(
      name: p.name,
      brand: p.brand,
      price: p.price,
      image: p.image,
      isCatalogSource: true,
    );
    for (int i = 0; i < p.quantity; i++) {
      cart.addProduct(product);
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${p.quantity}x ${p.name} ajoute au panier')),
    );
  }

  Widget _buildAssistantBubble(_ChatBubble msg) {
    final content = msg.content;
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFECECEC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Assistant', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Colors.black54)),
          const SizedBox(height: 6),
          Text(content, style: const TextStyle(fontSize: 16, height: 1.35)),
          if (msg.steps.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('Etapes', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            ...msg.steps.asMap().entries.map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('${e.key + 1}. ${e.value}'),
                )),
          ],
          if (msg.products.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('Produits recommandes', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ...msg.products.map(
              (p) => Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFFEAEAEA)),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.network(
                        p.image,
                        width: 56,
                        height: 56,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          width: 56,
                          height: 56,
                          color: const Color(0xFFF2F2F2),
                          alignment: Alignment.center,
                          child: const Icon(Icons.image_not_supported_outlined, size: 18),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(p.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                          Text('${p.brand} • ${p.price.toStringAsFixed(2)} TND', style: const TextStyle(fontSize: 12)),
                          if (p.reason.isNotEmpty)
                            Text(p.reason, style: const TextStyle(fontSize: 12, color: Colors.black54)),
                        ],
                      ),
                    ),
                    FilledButton.tonal(
                      onPressed: () => _addRecommendationToCart(p),
                      child: Text('Ajouter x${p.quantity}'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Assistant Recommandation'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 10, 16, 6),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF4F6),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFFFCBD4)),
              ),
              child: Text(
                'Agent actif: $_activeAgent • Ecrivez votre budget directement dans le message',
                style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.primaryRed),
              ),
            ),
            Expanded(
              child: _messages.isEmpty
                  ? const Center(child: Text('Ex: Je veux ma9rouna pour 25 TND'))
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final msg = _messages[index];
                        if (msg.isUser) {
                          return Align(
                            alignment: Alignment.centerRight,
                            child: Container(
                              margin: const EdgeInsets.symmetric(vertical: 6),
                              padding: const EdgeInsets.all(12),
                              constraints: const BoxConstraints(maxWidth: 300),
                              decoration: BoxDecoration(
                                color: AppTheme.primaryRed,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Text(msg.content, style: const TextStyle(color: Colors.white, fontSize: 16)),
                            ),
                          );
                        }
                        return _buildAssistantBubble(msg);
                      },
                    ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _messageController,
                      minLines: 1,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText: 'Ex: Nheb naamel ma9rouna b 20 TND',
                        border: OutlineInputBorder(),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: _sending ? null : _sendMessage,
                    child: _sending
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatBubble {
  final bool isUser;
  final String content;
  final List<String> steps;
  final List<AssistantRecommendedProduct> products;

  _ChatBubble.user(this.content)
      : isUser = true,
        steps = const [],
        products = const [];

  _ChatBubble.assistant(AssistantChatResponse response)
      : isUser = false,
        content = response.assistantMessage,
        steps = response.mode == 'full_recipe' ? const [] : response.steps,
        products = response.showProductsNow ? response.recommendedProducts : const [];

  _ChatBubble.assistantError(String message)
      : isUser = false,
        content = message,
        steps = const [],
        products = const [];
}

