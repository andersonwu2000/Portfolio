import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Pressable,
  Alert,
  StyleSheet,
} from "react-native";
import { useT } from "@/src/i18n";
import {
  bg,
  surface,
  surfaceLight,
  textPrimary,
  textSecondary,
  textPlaceholder,
  white,
  blue,
  blueDark,
  success,
  danger,
  dangerDark,
} from "@/src/theme/colors";

export interface OrderFormData {
  symbol: string;
  side: string;
  quantity: number;
  price: number;
}

interface OrderFormProps {
  onSubmit: (order: OrderFormData) => void;
  onCancel: () => void;
}

export function OrderForm({ onSubmit, onCancel }: OrderFormProps) {
  const { t } = useT();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");

  const handleSubmit = () => {
    const trimmedSymbol = symbol.trim().toUpperCase();
    if (!trimmedSymbol) {
      Alert.alert(t.common.error, t.orders.symbolRequired);
      return;
    }
    const qty = Number(quantity);
    if (!qty || qty <= 0) {
      Alert.alert(t.common.error, t.orders.quantityRequired);
      return;
    }
    const prc = Number(price);
    if (!prc || prc <= 0) {
      Alert.alert(t.common.error, t.orders.priceRequired);
      return;
    }

    const message = t.orders.confirmMessage
      .replace("{side}", side)
      .replace("{symbol}", trimmedSymbol)
      .replace("{quantity}", String(qty))
      .replace("{price}", prc.toFixed(2));

    Alert.alert(t.orders.confirmTitle, message, [
      { text: t.orders.cancel, style: "cancel" },
      {
        text: t.common.confirm,
        onPress: () =>
          onSubmit({ symbol: trimmedSymbol, side, quantity: qty, price: prc }),
      },
    ]);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t.orders.newOrder}</Text>

      {/* Side selector */}
      <View style={styles.sideRow}>
        <TouchableOpacity
          style={[styles.sideBtn, side === "BUY" && styles.sideBuyActive]}
          onPress={() => setSide("BUY")}
          testID="side-buy"
        >
          <Text
            style={[
              styles.sideText,
              side === "BUY" && styles.sideBuyTextActive,
            ]}
          >
            {t.orders.buy}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sideBtn, side === "SELL" && styles.sideSellActive]}
          onPress={() => setSide("SELL")}
          testID="side-sell"
        >
          <Text
            style={[
              styles.sideText,
              side === "SELL" && styles.sideSellTextActive,
            ]}
          >
            {t.orders.sell}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Symbol */}
      <Text style={styles.label}>{t.orders.symbol}</Text>
      <TextInput
        style={styles.input}
        value={symbol}
        onChangeText={setSymbol}
        placeholder="AAPL"
        placeholderTextColor={textPlaceholder}
        autoCapitalize="characters"
        testID="input-symbol"
      />

      {/* Quantity */}
      <Text style={styles.label}>{t.orders.qty}</Text>
      <TextInput
        style={styles.input}
        value={quantity}
        onChangeText={setQuantity}
        placeholder="100"
        placeholderTextColor={textPlaceholder}
        keyboardType="numeric"
        testID="input-quantity"
      />

      {/* Price */}
      <Text style={styles.label}>{t.orders.price}</Text>
      <TextInput
        style={styles.input}
        value={price}
        onChangeText={setPrice}
        placeholder="150.00"
        placeholderTextColor={textPlaceholder}
        keyboardType="decimal-pad"
        testID="input-price"
      />

      {/* Buttons */}
      <View style={styles.buttonRow}>
        <Pressable style={styles.cancelBtn} onPress={onCancel}>
          <Text style={styles.cancelText}>{t.orders.cancel}</Text>
        </Pressable>
        <Pressable style={styles.submitBtn} onPress={handleSubmit}>
          <Text style={styles.submitText}>{t.orders.submit}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: surface,
    borderRadius: 12,
    padding: 16,
    margin: 12,
  },
  title: {
    color: textPrimary,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 16,
  },
  sideRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 16,
  },
  sideBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: surfaceLight,
    alignItems: "center",
  },
  sideBuyActive: {
    backgroundColor: "rgba(34, 197, 94, 0.2)",
  },
  sideSellActive: {
    backgroundColor: "rgba(239, 68, 68, 0.2)",
  },
  sideText: {
    color: textSecondary,
    fontSize: 14,
    fontWeight: "600",
  },
  sideBuyTextActive: {
    color: success,
  },
  sideSellTextActive: {
    color: danger,
  },
  label: {
    color: textSecondary,
    fontSize: 13,
    marginBottom: 6,
  },
  input: {
    backgroundColor: bg,
    borderRadius: 8,
    padding: 12,
    color: textPrimary,
    fontSize: 15,
    marginBottom: 12,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 8,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: surfaceLight,
    alignItems: "center",
  },
  cancelText: {
    color: textSecondary,
    fontSize: 15,
    fontWeight: "600",
  },
  submitBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: blue,
    alignItems: "center",
  },
  submitText: {
    color: white,
    fontSize: 15,
    fontWeight: "700",
  },
});
