"""AutoFlow — FastAPI application entry point."""
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from core.config import settings
from core.telemetry import instrument_app
from storage.database import engine
from storage.models import Base
from schedules.manager import start_scheduler, stop_scheduler
from api.routes import oauth, workflows, executions, credentials, webhooks, triggers, schedules
from api.routes import orgs, versions, dlq, marketplace, privacy, billing, approvals, mcp_server
from api.routes import chat_messages, assistants, document_stores, api_keys, variables, leads, feedback
from api.routes import mcp_management, ai_builder, evaluations, policies, costs
from api.routes.auth import router as auth_router
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.idempotency import IdempotencyMiddleware

import integrations.core.nodes
import integrations.action_network.handler
import integrations.activecampaign.handler
import integrations.acuity_scheduling.handler
import integrations.adalo.handler
import integrations.affinity.handler
import integrations.agentflow.handler
import integrations.agentflow.nodes
import integrations.agents.handler
import integrations.agile_crm.handler
import integrations.ai.handler
import integrations.aircall.handler
import integrations.airparser.handler
import integrations.airtable.handler
import integrations.airtop.handler
import integrations.aitransform.handler
import integrations.algolia.handler
import integrations.amazon_bedrock.handler
import integrations.amazon_secrets_manager.handler
import integrations.amazon_ses.handler
import integrations.amazon_sns.handler
import integrations.amazon_sqs.handler
import integrations.amazon_textract.handler
import integrations.amqp.handler
import integrations.analytic.handler
import integrations.apify.handler
import integrations.apitable.handler
import integrations.apitemplate.handler
import integrations.apollo.handler
import integrations.asana_.handler
import integrations.ashby.handler
import integrations.askhandle.handler
import integrations.asknews.handler
import integrations.assembled.handler
import integrations.assemblyai.handler
import integrations.attio.handler
import integrations.autopilot.handler
import integrations.aws_s3_.handler
import integrations.azure_ad.handler
import integrations.azure_blob_storage.handler
import integrations.azure_communication_services.handler
import integrations.azure_devops.handler
import integrations.azure_openai.handler
import integrations.backblaze.handler
import integrations.bamboohr.handler
import integrations.bannerbear.handler
import integrations.baremetrics.handler
import integrations.baserow.handler
import integrations.beehiv.handler
import integrations.beeminder.handler
import integrations.bettermode.handler
import integrations.bigcommerce.handler
import integrations.billplz.handler
import integrations.binance.handler
import integrations.bitbucket.handler
import integrations.bitly.handler
import integrations.bitwarden.handler
import integrations.bland_ai.handler
import integrations.bluesky.handler
import integrations.bolna.handler
import integrations.bookedin.handler
import integrations.box.handler
import integrations.brandfetch.handler
import integrations.brevo.handler
import integrations.browser.handler
import integrations.bubble.handler
import integrations.buffer.handler
import integrations.buttondown.handler
import integrations.cache.handler
import integrations.cal.handler
import integrations.calendly.handler
import integrations.campaign_monitor.handler
import integrations.canny.handler
import integrations.canva.handler
import integrations.capsule_crm.handler
import integrations.carbone.handler
import integrations.cashfree_payments.handler
import integrations.certopus.handler
import integrations.chains.handler
import integrations.chargebee.handler
import integrations.chargekeeper.handler
import integrations.chatbase.handler
import integrations.chatling.handler
import integrations.chatwoot.handler
import integrations.chess_com.handler
import integrations.circle.handler
import integrations.circleci.handler
import integrations.cisco.handler
import integrations.clarifai.handler
import integrations.claude.handler
import integrations.clay.handler
import integrations.clearbit.handler
import integrations.clearouphone.handler
import integrations.clearout.handler
import integrations.clickfunnels.handler
import integrations.clicksend.handler
import integrations.clickup.handler
import integrations.clockify.handler
import integrations.clockodo.handler
import integrations.close.handler
import integrations.cloudconvert.handler
import integrations.cloudflare.handler
import integrations.cloudinary.handler
import integrations.cloutly.handler
import integrations.cockpit.handler
import integrations.coda.handler
import integrations.code.handler
import integrations.cody.handler
import integrations.cognito_forms.handler
import integrations.cohere.handler
import integrations.coingecko.handler
import integrations.compare_datasets.handler
import integrations.compression.handler
import integrations.confluence.handler
import integrations.connectuc.handler
import integrations.constant_contact.handler
import integrations.contentful.handler
import integrations.contextual_ai.handler
import integrations.convertkit.handler
import integrations.copper.handler
import integrations.copy_ai.handler
import integrations.coralogix.handler
import integrations.cortex.handler
import integrations.couchbase.handler
import integrations.coupa.handler
import integrations.cratedb.handler
import integrations.crisp.handler
import integrations.cron.handler
import integrations.crypto_.handler
import integrations.cryptolens.handler
import integrations.currents.handler
import integrations.cursor.handler
import integrations.customerio.handler
import integrations.customgpt.handler
import integrations.cyberark.handler
import integrations.dappier.handler
import integrations.dashworks.handler
import integrations.database.handler
import integrations.databricks.handler
import integrations.datadog.handler
import integrations.dataforb2b.handler
import integrations.datafuel.handler
import integrations.datatable.handler
import integrations.datetime_.handler
import integrations.datocms.handler
import integrations.debug_helper.handler
import integrations.deepgram.handler
import integrations.deepl.handler
import integrations.deepseek.handler
import integrations.deftform.handler
import integrations.demio.handler
import integrations.denser_ai.handler
import integrations.descript.handler
import integrations.detecting_ai.handler
import integrations.devin.handler
import integrations.dhl.handler
import integrations.digital_ocean.handler
import integrations.digital_pilot.handler
import integrations.dimo.handler
import integrations.discord.handler
import integrations.discourse.handler
import integrations.disqus.handler
import integrations.ditofeed.handler
import integrations.docsbot.handler
import integrations.doctly.handler
import integrations.document_loaders.handler
import integrations.documentpro.handler
import integrations.documerge.handler
import integrations.docusign.handler
import integrations.drift.handler
import integrations.drip.handler
import integrations.dropbox.handler
import integrations.dropcontact.handler
import integrations.drupal.handler
import integrations.dub.handler
import integrations.duckdb.handler
import integrations.dumpling_ai.handler
import integrations.dynamic_credential_check.handler
import integrations.e2e_test.handler
import integrations.easy_peasy_ai.handler
import integrations.echowin.handler
import integrations.eden_ai.handler
import integrations.edit_image.handler
import integrations.editionguard.handler
import integrations.egoi.handler
import integrations.elastic.handler
import integrations.elastic_email.handler
import integrations.elevenlabs.handler
import integrations.email_.handler
import integrations.email_read_imap.handler
import integrations.email_send.handler
import integrations.emailit.handler
import integrations.emailoctopus.handler
import integrations.embeddings.handler
import integrations.emelia.handler
import integrations.engine.handler
import integrations.enrichlayer.handler
import integrations.erpnext.handler
import integrations.error_trigger.handler
import integrations.esignatures.handler
import integrations.eth_name_service.handler
import integrations.evaluation.handler
import integrations.eventbrite.handler
import integrations.everhour.handler
import integrations.exa.handler
import integrations.execute_command.handler
import integrations.execute_workflow.handler
import integrations.execution_data.handler
import integrations.extracta_ai.handler
import integrations.facebook.handler
import integrations.facebook_lead_ads.handler
import integrations.facebook_pages.handler
import integrations.famulor.handler
import integrations.fathom.handler
import integrations.fathom_analytics.handler
import integrations.feathery.handler
import integrations.feedhive.handler
import integrations.fellow.handler
import integrations.figma.handler
import integrations.filemaker.handler
import integrations.files.handler
import integrations.filetopdf.handler
import integrations.fillout_forms.handler
import integrations.filter.handler
import integrations.fireberry.handler
import integrations.firecrawl.handler
import integrations.fireflies_ai.handler
import integrations.flipando.handler
import integrations.fliqr_ai.handler
import integrations.flow.handler
import integrations.flow_control.handler
import integrations.flow_helper.handler
import integrations.flow_parser.handler
import integrations.flowlu.handler
import integrations.folk.handler
import integrations.foreplay_co.handler
import integrations.form.handler
import integrations.formbricks.handler
import integrations.formio.handler
import integrations.formitable.handler
import integrations.formsite.handler
import integrations.formspark.handler
import integrations.formstack.handler
import integrations.fountain.handler
import integrations.fragment.handler
import integrations.frame.handler
import integrations.free_agent.handler
import integrations.freshdesk.handler
import integrations.freshsales.handler
import integrations.freshservice.handler
import integrations.freshworks_crm.handler
import integrations.frill.handler
import integrations.front.handler
import integrations.ftp.handler
import integrations.function.handler
import integrations.function_item.handler
import integrations.gameball.handler
import integrations.gamma.handler
import integrations.gcloud_pubsub.handler
import integrations.gender_api.handler
import integrations.generatebanners.handler
import integrations.getresponse.handler
import integrations.ghost.handler
import integrations.giftbit.handler
import integrations.gistly.handler
import integrations.git.handler
import integrations.gitea.handler
import integrations.github.handler
import integrations.gitlab.handler
import integrations.gladia.handler
import integrations.glide.handler
import integrations.gong.handler
import integrations.goodmem.handler
import integrations.google.sheets
import integrations.google.gmail
import integrations.google.drive
import integrations.google.calendar
import integrations.google_bigquery.handler
import integrations.google_cloud_storage.handler
import integrations.google_contacts.handler
import integrations.google_docs.handler
import integrations.google_forms.handler
import integrations.google_gemini.handler
import integrations.google_my_business.handler
import integrations.google_search.handler
import integrations.google_search_console.handler
import integrations.google_slides.handler
import integrations.google_tasks.handler
import integrations.google_vertexai.handler
import integrations.googlechat.handler
import integrations.gorgias.handler
import integrations.gotify.handler
import integrations.gotowebinar.handler
import integrations.gptzero_detect_ai.handler
import integrations.grafana.handler
import integrations.granola.handler
import integrations.graphql.handler
import integrations.graphs.handler
import integrations.gravityforms.handler
import integrations.greenhouse.handler
import integrations.greenpt.handler
import integrations.greip.handler
import integrations.griptape.handler
import integrations.grist.handler
import integrations.grok_xai.handler
import integrations.groq.handler
import integrations.guidelite.handler
import integrations.gumroad.handler
import integrations.hackernews.handler
import integrations.halopsa.handler
import integrations.harvest.handler
import integrations.hashi_corp_vault.handler
import integrations.hastewire.handler
import integrations.heartbeat.handler
import integrations.hedy.handler
import integrations.helpscout.handler
import integrations.heygen.handler
import integrations.heymarket_sms.handler
import integrations.highlevel.handler
import integrations.home_assistant.handler
import integrations.hootsuite.handler
import integrations.housecall_pro.handler
import integrations.html.handler
import integrations.htmlextract.handler
import integrations.http_oauth2.handler
import integrations.httprequest.handler
import integrations.hubspot.handler
import integrations.hugging_face.handler
import integrations.humanticai.handler
import integrations.hume_ai.handler
import integrations.hunter.handler
import integrations.hystruct.handler
import integrations.ibm_cognose.handler
import integrations.icalendar.handler
import integrations.if_node.handler
import integrations.iloveapi.handler
import integrations.image_router.handler
import integrations.imap.handler
import integrations.imeetify.handler
import integrations.influencers_club.handler
import integrations.insightly.handler
import integrations.insighto_ai.handler
import integrations.insta_charts.handler
import integrations.instabase.handler
import integrations.instagram_business.handler
import integrations.instantly_ai.handler
import integrations.instasent.handler
import integrations.intercom.handler
import integrations.interval.handler
import integrations.intruder.handler
import integrations.invoiceninja.handler
import integrations.item_lists.handler
import integrations.iterable.handler
import integrations.jenkins.handler
import integrations.jinaai.handler
import integrations.jira_.handler
import integrations.jogg_ai.handler
import integrations.jotform.handler
import integrations.jungle_grid.handler
import integrations.just_invoice.handler
import integrations.jwt.handler
import integrations.kafka.handler
import integrations.kallabot_ai.handler
import integrations.kapso.handler
import integrations.katana.handler
import integrations.keap.handler
import integrations.kimai.handler
import integrations.kissflow.handler
import integrations.kizeo_forms.handler
import integrations.klaviyo.handler
import integrations.klenty.handler
import integrations.knack.handler
import integrations.knock.handler
import integrations.ko_fi.handler
import integrations.kobotoolbox.handler
import integrations.kommo.handler
import integrations.kudosily.handler
import integrations.kustomer.handler
import integrations.ldap.handler
import integrations.lead_connector.handler
import integrations.leap_ai.handler
import integrations.lemlist.handler
import integrations.lemon_squeezy.handler
import integrations.letmepost.handler
import integrations.letta.handler
import integrations.lever.handler
import integrations.lightfunnels.handler
import integrations.line.handler
import integrations.linear.handler
import integrations.lingvanex.handler
import integrations.linkedin.handler
import integrations.llm.handler
import integrations.llmrails.handler
import integrations.local_file_trigger.handler
import integrations.localai.handler
import integrations.lofty.handler
import integrations.logrocket.handler
import integrations.logsnag.handler
import integrations.lokalise.handler
import integrations.lonescale.handler
import integrations.loops.handler
import integrations.lusha.handler
import integrations.magento.handler
import integrations.magical_api.handler
import integrations.magicslides.handler
import integrations.mailchain.handler
import integrations.mailcheck.handler
import integrations.mailchimp.handler
import integrations.mailercheck.handler
import integrations.mailerlite.handler
import integrations.mailerroo.handler
import integrations.mailgun.handler
import integrations.mailjet.handler
import integrations.mandrill.handler
import integrations.manual_trigger.handler
import integrations.manus.handler
import integrations.manychat.handler
import integrations.markdown.handler
import integrations.marketstack.handler
import integrations.mastodon.handler
import integrations.matomo.handler
import integrations.matrix.handler
import integrations.mattermost.handler
import integrations.mautic.handler
import integrations.mcp_.handler
import integrations.medium.handler
import integrations.meetgeek_ai.handler
import integrations.meistertask.handler
import integrations.mem.handler
import integrations.memory.handler
import integrations.mempool_space.handler
import integrations.merge_node.handler
import integrations.message_an_agent.handler
import integrations.messagebird.handler
import integrations.metabase.handler
import integrations.metatext.handler
import integrations.microsoft_365_people.handler
import integrations.microsoft_365_planner.handler
import integrations.microsoft_copilot.handler
import integrations.microsoft_dynamics_365_business_central.handler
import integrations.microsoft_dynamics_crm.handler
import integrations.microsoft_excel_365.handler
import integrations.microsoft_onedrive.handler
import integrations.microsoft_onenote.handler
import integrations.microsoft_outlook.handler
import integrations.microsoft_outlook_calendar.handler
import integrations.microsoft_power_bi.handler
import integrations.microsoft_sharepoint.handler
import integrations.microsoft_sql_server.handler
import integrations.microsoft_teams.handler
import integrations.microsoft_teams_bot.handler
import integrations.microsoft_todo.handler
import integrations.millionverifier.handler
import integrations.mind_studio.handler
import integrations.mindee.handler
import integrations.misp.handler
import integrations.missive.handler
import integrations.mistralai.handler
import integrations.mixmax.handler
import integrations.mixpanel.handler
import integrations.mocean.handler
import integrations.modelslab.handler
import integrations.moderation.handler
import integrations.mollie.handler
import integrations.monday.handler
import integrations.mongodb.handler
import integrations.monicacrm.handler
import integrations.moonclerk.handler
import integrations.mooninvoice.handler
import integrations.motion.handler
import integrations.move_binary_data.handler
import integrations.moveo_ai.handler
import integrations.moxie_crm.handler
import integrations.mqtt.handler
import integrations.msg91.handler
import integrations.multiagents.handler
import integrations.murf_api.handler
import integrations.mysendingbox.handler
import integrations.mysql.handler
import integrations.n8n_node.handler
import integrations.n8n_training_datastore.handler
import integrations.n8n_training_messenger.handler
import integrations.n8n_trigger.handler
import integrations.nasa.handler
import integrations.netlify.handler
import integrations.netscaler.handler
import integrations.netsuite.handler
import integrations.neverbounce.handler
import integrations.nextcloud.handler
import integrations.nifty.handler
import integrations.ninjapipe.handler
import integrations.ninox.handler
import integrations.nocodb.handler
import integrations.noop.handler
import integrations.notion.handler
import integrations.npm_node.handler
import integrations.ntly.handler
import integrations.nuelink.handler
import integrations.octopush_sms.handler
import integrations.odoo.handler
import integrations.okta.handler
import integrations.omnisend.handler
import integrations.oncehub.handler
import integrations.onesimpleapi.handler
import integrations.onfleet.handler
import integrations.open_router.handler
import integrations.openai.handler
import integrations.openmic_ai.handler
import integrations.openthesaurus.handler
import integrations.openweathermap.handler
import integrations.opnform.handler
import integrations.opportify.handler
import integrations.oracle.handler
import integrations.oracle_database.handler
import integrations.oracle_fusion_cloud_erp.handler
import integrations.orbit.handler
import integrations.orimon.handler
import integrations.oura.handler
import integrations.outputparsers.handler
import integrations.outseta.handler
import integrations.paddle.handler
import integrations.pagerduty_.handler
import integrations.pandadoc.handler
import integrations.paperform.handler
import integrations.parallel.handler
import integrations.parser_expert.handler
import integrations.parseur.handler
import integrations.pastebin.handler
import integrations.pastefy.handler
import integrations.paypal.handler
import integrations.paywhirl.handler
import integrations.pdf4me.handler
import integrations.pdf_co.handler
import integrations.pdfcrowd.handler
import integrations.pdfmonkey.handler
import integrations.peekalink.handler
import integrations.peekshot.handler
import integrations.pendo.handler
import integrations.perplexity.handler
import integrations.personal_ai.handler
import integrations.phantombuster.handler
import integrations.philipshue.handler
import integrations.phone_validator.handler
import integrations.photoroom.handler
import integrations.pinch_payments.handler
import integrations.pinecone.handler
import integrations.pinterest.handler
import integrations.pipedrive.handler
import integrations.placid.handler
import integrations.plausible.handler
import integrations.plivo.handler
import integrations.plunk.handler
import integrations.pocketbase.handler
import integrations.podio.handler
import integrations.pollybot_ai.handler
import integrations.polydoc.handler
import integrations.poper.handler
import integrations.postbin.handler
import integrations.postgres.handler
import integrations.posthog.handler
import integrations.postiz.handler
import integrations.postmark.handler
import integrations.predict_leads.handler
import integrations.predis_ai.handler
import integrations.presentation.handler
import integrations.productboard.handler
import integrations.produktly.handler
import integrations.profitwell.handler
import integrations.promotekit.handler
import integrations.prompthub.handler
import integrations.promptmate.handler
import integrations.prompts.handler
import integrations.provenexpert.handler
import integrations.proxycurl.handler
import integrations.pubrio.handler
import integrations.pushbullet.handler
import integrations.pushcut.handler
import integrations.pushover.handler
import integrations.pylon.handler
import integrations.qawafel.handler
import integrations.qdrant.handler
import integrations.quaderno.handler
import integrations.questdb.handler
import integrations.queue.handler
import integrations.quickbase.handler
import integrations.quickbooks.handler
import integrations.quickbooks_desktop_conductor.handler
import integrations.quickbooks_sandbox.handler
import integrations.quickchart.handler
import integrations.quickzu.handler
import integrations.quizell.handler
import integrations.qwilr.handler
import integrations.rabbitmq.handler
import integrations.raia_ai.handler
import integrations.raindrop.handler
import integrations.rapidtext_ai.handler
import integrations.razorpay.handler
import integrations.reachinbox.handler
import integrations.read_binary_file.handler
import integrations.read_binary_files.handler
import integrations.read_pdf.handler
import integrations.readwise.handler
import integrations.recall_ai.handler
import integrations.recordmanager.handler
import integrations.recurly.handler
import integrations.reddit.handler
import integrations.redis_node.handler
import integrations.rename_keys.handler
import integrations.rendex.handler
import integrations.reon_verifier.handler
import integrations.reply_io.handler
import integrations.resend.handler
import integrations.respaid.handler
import integrations.respond_io.handler
import integrations.respond_to_webhook.handler
import integrations.responsesynthesizer.handler
import integrations.retable.handler
import integrations.retell_ai.handler
import integrations.retrievers.handler
import integrations.retune.handler
import integrations.returning_ai.handler
import integrations.ringcentral.handler
import integrations.robolly.handler
import integrations.rocketchat.handler
import integrations.roe_ai.handler
import integrations.rounded_studio.handler
import integrations.rss.handler
import integrations.rss_feed_read.handler
import integrations.rundeck.handler
import integrations.runware.handler
import integrations.runway.handler
import integrations.saastic.handler
import integrations.saleor.handler
import integrations.salesforce.handler
import integrations.salesloft.handler
import integrations.salesmate.handler
import integrations.sap_ariba.handler
import integrations.sardis.handler
import integrations.savvycal.handler
import integrations.scenario.handler
import integrations.schedule.handler
import integrations.scrapegrapghai.handler
import integrations.scrapeless.handler
import integrations.seatable.handler
import integrations.security_scorecard.handler
import integrations.seek_table.handler
import integrations.segment.handler
import integrations.send_it.handler
import integrations.sender.handler
import integrations.sendfox.handler
import integrations.sendgrid.handler
import integrations.sendinblue.handler
import integrations.sendpulse.handler
import integrations.sendr.handler
import integrations.sendy.handler
import integrations.senja.handler
import integrations.sentrylo.handler
import integrations.sequentialagents.handler
import integrations.serp_api.handler
import integrations.serpstat.handler
import integrations.servicenow.handler
import integrations.sessions_us.handler
import integrations.set_node.handler
import integrations.seven.handler
import integrations.shippo.handler
import integrations.shopify.handler
import integrations.short_io.handler
import integrations.sign_now.handler
import integrations.signl4.handler
import integrations.signrequest.handler
import integrations.simplepdf.handler
import integrations.simpliroute.handler
import integrations.simplybookme.handler
import integrations.simplyprint.handler
import integrations.simulate.handler
import integrations.sitespeakai.handler
import integrations.skyprep.handler
import integrations.skyvern.handler
import integrations.slack.handler
import integrations.slashed.handler
import integrations.slidespeak.handler
import integrations.slite.handler
import integrations.smaily.handler
import integrations.smartlead.handler
import integrations.smartsheet.handler
import integrations.smartsuite.handler
import integrations.smoove.handler
import integrations.sms77.handler
import integrations.smsmode.handler
import integrations.snowflake.handler
import integrations.soap.handler
import integrations.socialkit.handler
import integrations.softr.handler
import integrations.sofya.handler
import integrations.speechtotext.handler
import integrations.sperse.handler
import integrations.split_in_batches.handler
import integrations.splitwise.handler
import integrations.splunk.handler
import integrations.spotify.handler
import integrations.spreadsheet_file.handler
import integrations.square.handler
import integrations.sse_trigger.handler
import integrations.ssh.handler
import integrations.stability_ai.handler
import integrations.stable_diffusion_webui.handler
import integrations.stackby.handler
import integrations.sticky_note.handler
import integrations.stop_and_error.handler
import integrations.storyblok.handler
import integrations.straico.handler
import integrations.strale.handler
import integrations.strapi.handler
import integrations.strava.handler
import integrations.streak.handler
import integrations.stripe_.handler
import integrations.supabase.handler
import integrations.supabase_data.handler
import integrations.supadata.handler
import integrations.surrealdb.handler
import integrations.surveymonkey.handler
import integrations.surveytale.handler
import integrations.swarmnode.handler
import integrations.switch_node.handler
import integrations.syncromsp.handler
import integrations.synthesia.handler
import integrations.systeme_io.handler
import integrations.tableau.handler
import integrations.taiga.handler
import integrations.talkable.handler
import integrations.tally.handler
import integrations.tapfiliate.handler
import integrations.tarvent.handler
import integrations.taskade.handler
import integrations.tavily.handler
import integrations.teable.handler
import integrations.teamhood.handler
import integrations.teamleader.handler
import integrations.teamwork.handler
import integrations.telegram.handler
import integrations.telegram_bot.handler
import integrations.telnyx.handler
import integrations.tenzo.handler
import integrations.text_splitters.handler
import integrations.textcortex_ai.handler
import integrations.thankster.handler
import integrations.thehive.handler
import integrations.thehiveproject.handler
import integrations.ticktick.handler
import integrations.tidely.handler
import integrations.tidycal.handler
import integrations.time_ops.handler
import integrations.timelines_ai.handler
import integrations.timesaved.handler
import integrations.timescaledb.handler
import integrations.tiny_talk_ai.handler
import integrations.tl_dv.handler
import integrations.todoist.handler
import integrations.toggl.handler
import integrations.tools.handler
import integrations.totp.handler
import integrations.transform.handler
import integrations.travisci.handler
import integrations.trello_.handler
import integrations.truelayer.handler
import integrations.twake.handler
import integrations.twenty.handler
import integrations.twilio_.handler
import integrations.twist.handler
import integrations.twitch.handler
import integrations.twitter.handler
import integrations.typeform.handler
import integrations.typefully.handler
import integrations.umami.handler
import integrations.unleashedsoftware.handler
import integrations.uplead.handler
import integrations.uproc.handler
import integrations.uptime_robot.handler
import integrations.urlscanio.handler
import integrations.utilities.handler
import integrations.validatedemails.handler
import integrations.vector.handler
import integrations.vectorstores.handler
import integrations.venafi.handler
import integrations.vercel.handler
import integrations.vero.handler
import integrations.vidlab7.handler
import integrations.vidnoz.handler
import integrations.vimeo.handler
import integrations.vonage.handler
import integrations.vouchery_io.handler
import integrations.wait.handler
import integrations.wealthbox.handler
import integrations.webex.handler
import integrations.webflow.handler
import integrations.webhook.handler
import integrations.wekan.handler
import integrations.whatsapp.handler
import integrations.wise.handler
import integrations.wistia.handler
import integrations.wonderchat.handler
import integrations.woocommerce.handler
import integrations.woodpecker.handler
import integrations.wordpress.handler
import integrations.workday.handler
import integrations.workflow_trigger.handler
import integrations.wrike.handler
import integrations.write_binary_file.handler
import integrations.wufoo.handler
import integrations.xero.handler
import integrations.xml.handler
import integrations.yourls.handler
import integrations.youtrack.handler
import integrations.youtube.handler
import integrations.zammad.handler
import integrations.zendesk.handler
import integrations.zerobounce.handler
import integrations.zoho.handler
import integrations.zoho_crm.handler
import integrations.zoom.handler
import integrations.zulip.handler
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await start_scheduler()
    log.info("autoflow_started", env=settings.APP_ENV)
    yield
    await stop_scheduler()
    await engine.dispose()
    log.info("autoflow_stopped")


app = FastAPI(
    title="AutoFlow",
    description="Production-grade workflow automation platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
# CORS: a wildcard origin combined with allow_credentials=True is invalid per
# the CORS spec — browsers silently reject it. In debug mode we allow
# common local dev origins; in production we allow only APP_BASE_URL
# (and FRONTEND_URL if it differs, e.g. when the SPA is on a separate
# domain/port from the API).
_cors_origins: list[str] = []
if settings.DEBUG:
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        settings.APP_BASE_URL,
    ]
else:
    _cors_origins = [settings.APP_BASE_URL]

if settings.FRONTEND_URL and settings.FRONTEND_URL not in _cors_origins:
    _cors_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

instrument_app(app)

app.include_router(auth_router)
app.include_router(oauth.router,       prefix="/oauth",           tags=["OAuth"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["Credentials"])
app.include_router(workflows.router,   prefix="/api/workflows",   tags=["Workflows"])
app.include_router(versions.router,    prefix="/api/workflows",   tags=["Workflow Versioning"])
app.include_router(executions.router,  prefix="/api/executions",  tags=["Executions"])
app.include_router(triggers.router,    prefix="/api/triggers",    tags=["Triggers"])
app.include_router(schedules.router,   prefix="/api/schedules",   tags=["Schedules"])
app.include_router(webhooks.router,    prefix="/webhooks",        tags=["Webhooks"])
app.include_router(orgs.router,        prefix="/api/orgs",        tags=["Organizations"])
app.include_router(dlq.router,         prefix="/api/dlq",         tags=["Dead Letter Queue"])
app.include_router(marketplace.router, prefix="/api/marketplace", tags=["Marketplace"])
app.include_router(privacy.router)
app.include_router(billing.router)
app.include_router(approvals.router)
app.include_router(mcp_server.router)
app.include_router(chat_messages.router, prefix="/api/chat-messages",   tags=["Chat Messages"])
app.include_router(assistants.router,    prefix="/api/assistants",      tags=["Assistants"])
app.include_router(document_stores.router, prefix="/api/document-stores", tags=["Document Stores"])
app.include_router(api_keys.router,      prefix="/api/api-keys",        tags=["API Keys"])
app.include_router(variables.router,     prefix="/api/variables",       tags=["Variables"])
app.include_router(leads.router,         prefix="/api/leads",           tags=["Leads"])
app.include_router(feedback.router,      prefix="/api/feedback",        tags=["Feedback"])
app.include_router(mcp_management.router, prefix="/api/mcp/management",  tags=["MCP Management"])
app.include_router(ai_builder.router,     prefix="/api/ai-builder",      tags=["AI Builder"])
app.include_router(evaluations.router,    prefix="/api/evaluations",     tags=["Evaluations"])
app.include_router(policies.router,       prefix="/api/policies",        tags=["Policies"])
app.include_router(costs.router,          prefix="/api/costs",           tags=["Costs"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/api/providers", tags=["OAuth"])
async def list_providers(response: Response):
    # Static per-deploy (the provider list only changes when code changes,
    # never per-request or per-user) — safe to cache at the edge/browser.
    response.headers["Cache-Control"] = "public, max-age=300"
    from oauth.providers import PROVIDERS
    return {"providers": [
        {"name": p.name, "display_name": p.display_name,
         "icon": p.icon, "scopes": p.default_scopes}
        for p in PROVIDERS.values()
    ]}


@app.get("/api/node-types", tags=["Workflows"])
async def list_node_types(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    from core.execution_engine import NODE_HANDLERS
    return {"node_types": sorted(NODE_HANDLERS.keys())}