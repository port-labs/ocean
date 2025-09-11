---
title: Integration Resync Triggers
sidebar_label: 🕹️ Integration Resync Triggers
sidebar_position: 9
---

import ResyncAbortMessage from '@site/docs/_common/resync-abort-message.mdx';

# 🕹️ Integration Resync Triggers

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import SwaggerGuide from './\_mdx/trigger-swagger-guide.md';
import CurlGuide from './\_mdx/trigger-curl-guide.md';
import PythonGuide from './\_mdx/trigger-python-guide.md';

This guide explains how you can trigger your integration using [Port](https://app.getport.io).

After setting up & running your integration, you can trigger resyncs using Port's UI/API. You can also trigger resyncs by setting `scheduledResyncInterval` in the integration environment variables.

Triggering your integration will run the integration resync and will resync all the data from the source into port and
creating new data, update existing data and delete data that no longer exists in the source by doing so.

<ResyncAbortMessage />

## Triggering using Port's UI

1. Login to [Port](https://app.getport.io) and browse to the [builder page](https://app.port.io/data-model).

2. Click on the [Data Sources](https://app.port.io/settings/data-sources) tab.

3. Use the search bar to find the integration you want to trigger a resync for.

   ![Ingest Button](@site/static/img/ingest-button-1.png)

3. Select the integration you want to trigger a resync for from the list of your installed integrations.
4. Click on the `Resync` button.

   ![Installation Page](@site/static/img/resync-button.png)

## Triggering using Port's API

By patching the integration either with a new configuration or by patching it with no changes, The integration will
detect the trigger and perform a resync.

<Tabs>
    <TabItem value="swagger" label="Swagger" default>
        <SwaggerGuide/>
    </TabItem>
    <TabItem value="curl" label="cURL">
        <CurlGuide/>
    </TabItem>
    <TabItem value="python" label="Python">
        <PythonGuide/>
    </TabItem>
</Tabs>

## Handling Incomplete Resyncs

Ocean is designed to handle incomplete resyncs gracefully to prevent data loss. When a resync is interrupted, either due to a fatal error, unhandled exception, or a new resync being triggered before the previous one completes, Ocean will take the following actions:

1. If an error occurs during the resync of a specific kind, Ocean will:
   - Stop the data ingestion for the current kind
   - Move on to the next kind in the sequence
   - Continue processing remaining kinds
   - Skip the delete phase

2. When a new resync is triggered while another is in progress:
   - The ongoing resync will be terminated
   - A new resync will start immediately
   - This behavior ensures that your data stays current and prevents potential conflicts

This approach prioritizes data safety by ensuring that no data is accidentally deleted during interrupted resyncs. While this means that some stale data might temporarily remain in your catalog, it's a deliberate design choice to prevent data loss. The next successful resync will clean up any remaining stale data.

:::tip Interrupted Resyncs
If you notice that resyncs are frequently being interrupted, consider adjusting your `scheduledResyncInterval` to a longer duration to allow each resync to complete fully.
:::
