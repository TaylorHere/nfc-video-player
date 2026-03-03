import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_app/main.dart';

void main() {
  testWidgets('App launches with scan tab', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('NFC 安全播放'), findsOneWidget);
    expect(find.text('扫描'), findsOneWidget);
  });
}
