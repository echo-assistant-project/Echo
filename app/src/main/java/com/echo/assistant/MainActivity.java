package com.echo.assistant;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.ContactsContract;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int SPEECH = 10, CONTACTS = 11, CALL = 1, TEXT = 2;
    private int pendingAction;
    private String pendingName = "", pendingMessage = "";
    private TextView transcript, status;
    private EditText input;
    private TextToSpeech tts;
    private boolean ttsReady;
    private final int cyan = Color.rgb(70, 226, 255), muted = Color.rgb(150, 177, 194), panel = Color.rgb(10, 22, 37);

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.rgb(4,10,19)); getWindow().setNavigationBarColor(Color.rgb(4,10,19));
        tts = new TextToSpeech(this, result -> { if (result == TextToSpeech.SUCCESS) { tts.setLanguage(Locale.US); tts.setPitch(1.0f); tts.setSpeechRate(.9f); ttsReady = true; } });
        buildUi();
    }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(1); root.setFitsSystemWindows(true); root.setPadding(dp(22),dp(24),dp(22),dp(20)); root.setBackgroundColor(Color.rgb(4,10,19));
        TextView brand = label("E C H O",15,cyan,true); root.addView(brand);
        TextView title = label("Your phone, hands-free.",28,Color.WHITE,true); title.setPadding(0,dp(10),0,dp(6)); root.addView(title);
        root.addView(label("Standalone voice controls · no PC or FreeLLMAPI required",14,muted,false));
        Button orbPreview = new Button(this); orbPreview.setText("Open Echo orb preview"); orbPreview.setAllCaps(false);
        orbPreview.setOnClickListener(v -> startActivity(new Intent(this, FloatingOrbComposeActivity.class)));
        root.addView(orbPreview);
        status = label("READY  ·  Tap the mic to speak",13,cyan,false); status.setPadding(0,dp(24),0,dp(10)); root.addView(status);
        ScrollView scroll = new ScrollView(this); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        transcript = label("Try saying:\n\n• Open YouTube\n• Call Alex\n• Text Alex saying I’m on my way\n\nCalls open the dialer. Texts open your messaging app with the message ready for you to review and send.",17,Color.rgb(226,241,250),false);
        transcript.setLineSpacing(dp(5),1f); transcript.setPadding(dp(18),dp(18),dp(18),dp(18)); transcript.setBackgroundColor(panel); scroll.addView(transcript);
        input = new EditText(this); input.setSingleLine(true); input.setHint("Or type a command…"); input.setHintTextColor(muted); input.setTextColor(Color.WHITE); input.setTextSize(16); input.setImeOptions(EditorInfo.IME_ACTION_SEND); input.setPadding(dp(14),dp(12),dp(14),dp(12)); input.setBackgroundTintList(android.content.res.ColorStateList.valueOf(cyan));
        input.setOnEditorActionListener((v,a,e)->{String s=input.getText().toString().trim(); if(!s.isEmpty()){input.setText("");handle(s);return true;}return false;});
        LinearLayout.LayoutParams ilp=new LinearLayout.LayoutParams(-1,-2); ilp.topMargin=dp(15); root.addView(input,ilp);
        Button mic=new Button(this); mic.setText("🎙   TALK TO ECHO"); mic.setTextColor(Color.rgb(3,18,28)); mic.setTextSize(14); mic.setTypeface(Typeface.DEFAULT,Typeface.BOLD); mic.setAllCaps(false); mic.setBackgroundTintList(android.content.res.ColorStateList.valueOf(cyan));
        LinearLayout.LayoutParams mlp=new LinearLayout.LayoutParams(-1,dp(58)); mlp.topMargin=dp(14); root.addView(mic,mlp); mic.setOnClickListener(v->listen());
        TextView note=label("Speech recognition uses the phone’s speech service. Calls and texts are shown for your review before sending.",12,muted,false); note.setGravity(Gravity.CENTER); note.setPadding(dp(8),dp(12),dp(8),0); root.addView(note);
        setContentView(root);
    }
    private TextView label(String text,int size,int color,boolean bold){TextView v=new TextView(this);v.setText(text);v.setTextColor(color);v.setTextSize(size);if(bold)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return v;}
    private void listen(){Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);i.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"en-IN");i.putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak a command for Echo");i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,3);try{startActivityForResult(i,SPEECH);status.setText("LISTENING  ·  Say a command");}catch(ActivityNotFoundException e){status.setText("No speech service is available on this phone.");}}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==SPEECH&&result==RESULT_OK&&data!=null){ArrayList<String> r=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(r!=null&&!r.isEmpty())handle(r.get(0));else status.setText("I didn’t catch that. Try again.");}}
    private void handle(String raw){String cmd=raw.trim(),lo=cmd.toLowerCase(Locale.ROOT);transcript.setText("YOU SAID\n\n“"+cmd+"”");status.setText("COMMAND  ·  Reviewing request");
        if(lo.matches("^(open|launch|start)\\s+.+")){String app=lo.replaceFirst("^(open|launch|start)\\s+","").replaceAll("\\s+on my phone$","").trim();say("On it, boss.");openApp(app);return;}
        if(lo.matches("^(call|phone|ring)\\s+.+")){pendingAction=CALL;pendingName=cmd.replaceFirst("(?i)^(call|phone|ring)\\s+","").trim();say("On it, boss.");requestContacts();return;}
        if(lo.matches("^(text|message|sms)\\s+.+")){String rest=cmd.replaceFirst("(?i)^(text|message|sms)\\s+","");java.util.regex.Matcher m=java.util.regex.Pattern.compile("(?i)^(.+?)\\s+(?:saying|that says|message)\\s+(.+)$").matcher(rest);if(!m.matches()){reply("Try: ‘Text Alex saying I’m on my way.’ I’ll prepare it for you to review.");return;}pendingAction=TEXT;pendingName=m.group(1).trim();pendingMessage=m.group(2).trim();say("On it, boss.");requestContacts();return;}
        if(lo.equals("stop")||lo.equals("cancel")){if(tts!=null)tts.stop();status.setText("STOPPED");return;}
        reply("I can open an app, start a call, or prepare a text. Try ‘Open Maps’ or ‘Text Alex saying I’m outside.’");
    }
    private void openApp(String name){PhoneActionRouter.Result result=PhoneActionRouter.tryHandle(this,"open "+name);status.setText(result.getMessage());transcript.setText(result.getMessage());if(result.getHandled())say(result.getMessage());}
    private void requestContacts(){if(checkSelfPermission(Manifest.permission.READ_CONTACTS)==PackageManager.PERMISSION_GRANTED)findContact();else requestPermissions(new String[]{Manifest.permission.READ_CONTACTS},CONTACTS);}
    @Override public void onRequestPermissionsResult(int request,String[] p,int[] g){super.onRequestPermissionsResult(request,p,g);if(request==CONTACTS){if(g.length>0&&g[0]==PackageManager.PERMISSION_GRANTED)findContact();else{status.setText("Contacts permission was not granted.");reply("I need contacts permission to find that person. No call or text was started.");}}}
    private String findNumber(String wanted){Cursor c=null;try{c=getContentResolver().query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,new String[]{ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,ContactsContract.CommonDataKinds.Phone.NUMBER},null,null,ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME+" COLLATE NOCASE ASC");if(c==null)return null;String partial=null;while(c.moveToNext()){String n=c.getString(0),num=c.getString(1);if(n==null||num==null)continue;if(n.equalsIgnoreCase(wanted))return num;if(n.toLowerCase(Locale.ROOT).contains(wanted.toLowerCase(Locale.ROOT))&&partial==null)partial=num;}return partial;}catch(SecurityException e){return null;}finally{if(c!=null)c.close();}}
    private void findContact(){String number=findNumber(pendingName);if(number==null){status.setText("Couldn’t find a phone number for “"+pendingName+"”.");reply("I couldn’t find a number for "+pendingName+". Check the contact name and try again.");return;}try{if(pendingAction==CALL){status.setText("CALL READY  ·  Review in your dialer");startActivity(new Intent(Intent.ACTION_DIAL,Uri.fromParts("tel",number,null)));}else{status.setText("TEXT READY  ·  Review and send in your messaging app");Intent i=new Intent(Intent.ACTION_SENDTO,Uri.fromParts("smsto",number,null));i.putExtra("sms_body",pendingMessage);startActivity(i);}}catch(ActivityNotFoundException e){status.setText("No dialer or messaging app could handle that action.");}}
    private void reply(String s){status.setText("ECHO  ·  Reply");transcript.setText(s);say(s);}
    private void say(String s){if(ttsReady)tts.speak(s,TextToSpeech.QUEUE_FLUSH,null,"echo-reply");}
    @Override protected void onDestroy(){if(tts!=null){tts.stop();tts.shutdown();}super.onDestroy();}
}
