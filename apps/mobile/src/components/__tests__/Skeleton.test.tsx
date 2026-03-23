import React from "react";
import { render } from "@testing-library/react-native";
import { Skeleton, MetricCardSkeleton } from "../Skeleton";

// Mock Animated to avoid native animation issues in tests
jest.mock("react-native/Libraries/Animated/NativeAnimatedHelper");

describe("Skeleton", () => {
  it("renders without crashing", () => {
    const { toJSON } = render(<Skeleton />);
    expect(toJSON()).not.toBeNull();
  });

  it("renders with custom width and height", () => {
    const { toJSON } = render(<Skeleton width={120} height={24} />);
    expect(toJSON()).not.toBeNull();
  });

  it("renders with percentage width", () => {
    const { toJSON } = render(<Skeleton width="50%" height={16} />);
    expect(toJSON()).not.toBeNull();
  });
});

describe("MetricCardSkeleton", () => {
  it("renders without crashing", () => {
    const { toJSON } = render(<MetricCardSkeleton />);
    expect(toJSON()).not.toBeNull();
  });

  it("renders two skeleton elements inside card", () => {
    const { toJSON } = render(<MetricCardSkeleton />);
    const tree = toJSON();
    // MetricCardSkeleton renders a View with two Animated.View children
    expect(tree).not.toBeNull();
    if (tree && "children" in tree) {
      expect(tree.children).toHaveLength(2);
    }
  });
});
