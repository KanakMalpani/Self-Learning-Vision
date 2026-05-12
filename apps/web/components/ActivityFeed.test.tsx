import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ActivityFeed from "@/components/ActivityFeed";
import type { ActivityEntry } from "@/types/memory";

const baseActivity: ActivityEntry = {
  stage: "uploaded",
  message: "Photo uploaded",
  created_at: "2026-03-29T12:00:00.000Z",
};

describe("ActivityFeed", () => {
  it("renders formatted stages and realtime badge", () => {
    render(
      <ActivityFeed
        activities={[baseActivity]}
        status="detecting"
        mode="sse"
      />
    );

    expect(screen.getAllByText(/Photo uploaded/i)).toHaveLength(2);
    expect(screen.getByText(/Live/i)).toBeInTheDocument();
    expect(screen.getByText(/detecting/i)).toBeInTheDocument();
  });

  it("shows idle empty state when no events", () => {
    render(<ActivityFeed activities={[]} status={null} mode="polling" />);

    expect(screen.getByText(/waiting for a memory run/i)).toBeInTheDocument();
    expect(screen.getByText(/Polling/i)).toBeInTheDocument();
  });
});

