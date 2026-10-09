import { afterEach, describe, expect, it } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
	collectUpstreamState,
	runStartupWatch,
	stateChanged,
	statusMessage,
	versionAtLeast,
	type WatchState,
} from "../bin/omp-upstream-watch";

const temporaryDirectories: string[] = [];

function response(body: unknown, status = 200) {
	return {
		ok: status >= 200 && status < 300,
		status,
		async json() {
			return body;
		},
		async text() {
			return typeof body === "string" ? body : JSON.stringify(body);
		},
	};
}

function fixtureFetch(overrides: Record<string, unknown> = {}) {
	return async (url: string) => {
		if (url.endsWith("/commits/main")) return response({ sha: "abc123456789" });
		if (url.includes("/tags?")) return response([{ name: "v18.8.6" }]);
		if (url.endsWith("/issues/8025")) return response({ state: "open", updated_at: "2026-10-09T00:00:00Z" });
		if (url.endsWith("/issues/5328")) return response({ state: "open", updated_at: "2026-07-13T00:00:00Z" });
		if (url.endsWith("/pulls/41086")) return response({ state: "closed", merged_at: "2026-09-03T10:41:21Z" });
		if (url.endsWith("/src/terminal.ts")) return response(overrides.terminalSource ?? "terminal source");
		if (url.endsWith("/test/terminal-disconnect-raw-mode-throw.test.ts")) {
			return response(overrides.terminalTest ?? "terminal regression");
		}
		throw new Error(`Unexpected URL ${url}`);
	};
}

afterEach(async () => {
	await Promise.all(temporaryDirectories.splice(0).map((directory) => rm(directory, { recursive: true, force: true })));
});

describe("OMP startup upstream watch", () => {
	it("recognizes the first Bun release line containing the Darwin EINTR retry", () => {
		expect(versionAtLeast("1.4.0", "1.4.1")).toBeFalse();
		expect(versionAtLeast("1.4.1", "1.4.1")).toBeTrue();
		expect(versionAtLeast("1.4.2", "1.4.1")).toBeTrue();
	});

	it("records evidence without declaring the whole incident permanently fixed", async () => {
		const state = await collectUpstreamState(fixtureFetch() as never, "1.4.2", new Date("2026-10-09T12:00:00Z"));
		expect(state.bunEintrRetryShipped).toBeTrue();
		expect(state.bunFix).toEqual({ state: "closed", mergedAt: "2026-09-03T10:41:21Z" });
		expect(state.permanentStatus).toBe("UNRESOLVED");
		expect(state.terminalSourceSha256).toHaveLength(64);
	});

	it("requests review when watched source or issue state changes", async () => {
		const previous = await collectUpstreamState(fixtureFetch() as never, "1.4.2", new Date("2026-10-09T12:00:00Z"));
		const current = { ...previous, terminalSourceSha256: "f".repeat(64) } satisfies WatchState;
		expect(stateChanged(previous, current)).toBeTrue();
		expect(statusMessage(current, true).text).toContain("Run “omp-concierge upstream-watch”");
	});

	it("uses a fresh cache without making startup depend on GitHub", async () => {
		const directory = await mkdtemp(join(tmpdir(), "omp-upstream-watch-"));
		temporaryDirectories.push(directory);
		const statePath = join(directory, "state.json");
		const notifications: string[] = [];
		const context = { hasUI: true, ui: { notify: (message: string) => notifications.push(message) } };
		const now = new Date("2026-10-09T12:00:00Z");
		await runStartupWatch(context, { statePath, fetchImpl: fixtureFetch() as never, bunVersion: "1.4.2", now });
		await runStartupWatch(context, {
			statePath,
			fetchImpl: (async () => {
				throw new Error("network should not be called");
			}) as never,
			bunVersion: "1.4.2",
			now: new Date("2026-10-09T12:01:00Z"),
		});
		expect(notifications).toHaveLength(2);
		expect(notifications[1]).toContain("stdin-ended/raw-mode is still unresolved");
	});

	it("fails soft when GitHub is unavailable", async () => {
		const directory = await mkdtemp(join(tmpdir(), "omp-upstream-watch-"));
		temporaryDirectories.push(directory);
		const notifications: string[] = [];
		await expect(
			runStartupWatch(
				{ hasUI: true, ui: { notify: (message: string) => notifications.push(message) } },
				{
					statePath: join(directory, "state.json"),
					fetchImpl: (async () => {
						throw new Error("offline");
					}) as never,
					bunVersion: "1.4.2",
					now: new Date("2026-10-09T12:00:00Z"),
				},
			),
		).resolves.toBeUndefined();
		expect(notifications[0]).toContain("startup continues");
	});
});
