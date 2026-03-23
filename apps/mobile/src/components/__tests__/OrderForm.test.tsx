import React from "react";
import { Alert } from "react-native";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { OrderForm } from "../OrderForm";

// Mock i18n with English translations
jest.mock("../../i18n", () => ({
  useT: () => ({
    t: {
      common: { error: "Error", confirm: "Confirm", failed: "Failed" },
      orders: {
        newOrder: "New Order",
        buy: "Buy",
        sell: "Sell",
        submit: "Submit Order",
        cancel: "Cancel",
        confirmTitle: "Confirm Order",
        confirmMessage:
          "Place {side} order for {quantity} shares of {symbol} at ${price}?",
        symbol: "Symbol",
        qty: "Qty",
        price: "Price",
        symbolRequired: "Symbol is required",
        quantityRequired: "Quantity must be greater than 0",
        priceRequired: "Price must be greater than 0",
      },
    },
    lang: "en",
    setLang: jest.fn(),
  }),
}));

describe("OrderForm", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
  });

  it("renders all input fields and buttons", () => {
    render(<OrderForm onSubmit={jest.fn()} onCancel={jest.fn()} />);

    expect(screen.getByTestId("input-symbol")).toBeTruthy();
    expect(screen.getByTestId("input-quantity")).toBeTruthy();
    expect(screen.getByTestId("input-price")).toBeTruthy();
    expect(screen.getByText("Buy")).toBeTruthy();
    expect(screen.getByText("Sell")).toBeTruthy();
    expect(screen.getByText("Submit Order")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });

  it("shows confirmation Alert on submit with valid inputs", () => {
    const alertSpy = jest.spyOn(Alert, "alert").mockImplementation(() => {});
    render(<OrderForm onSubmit={jest.fn()} onCancel={jest.fn()} />);

    fireEvent.changeText(screen.getByTestId("input-symbol"), "AAPL");
    fireEvent.changeText(screen.getByTestId("input-quantity"), "100");
    fireEvent.changeText(screen.getByTestId("input-price"), "150.50");
    fireEvent.press(screen.getByText("Submit Order"));

    expect(alertSpy).toHaveBeenCalledWith(
      "Confirm Order",
      "Place BUY order for 100 shares of AAPL at $150.50?",
      expect.arrayContaining([
        expect.objectContaining({ text: "Cancel" }),
        expect.objectContaining({ text: "Confirm" }),
      ]),
    );
  });

  it("calls onSubmit with order data after confirmation", () => {
    // Mock Alert.alert to immediately invoke the confirm button (second button)
    jest.spyOn(Alert, "alert").mockImplementation((_title, _message, buttons) => {
      const confirmBtn = buttons?.[1];
      if (confirmBtn?.onPress) confirmBtn.onPress();
    });

    const onSubmit = jest.fn();
    render(<OrderForm onSubmit={onSubmit} onCancel={jest.fn()} />);

    fireEvent.changeText(screen.getByTestId("input-symbol"), "TSLA");
    fireEvent.changeText(screen.getByTestId("input-quantity"), "50");
    fireEvent.changeText(screen.getByTestId("input-price"), "200");
    fireEvent.press(screen.getByText("Submit Order"));

    expect(onSubmit).toHaveBeenCalledWith({
      symbol: "TSLA",
      side: "BUY",
      quantity: 50,
      price: 200,
    });
  });
});
